$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path
$probeDir = $PSScriptRoot
$envPath = Join-Path $repoRoot ".env"
$imagePath = Join-Path $probeDir "synthetic_test_document.png"
$resultPath = Join-Path $probeDir "probe_result.safe.json"

function Load-DotEnv {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    foreach ($line in [System.IO.File]::ReadLines($Path)) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith("#")) {
            continue
        }
        $idx = $trimmed.IndexOf("=")
        if ($idx -lt 1) {
            continue
        }
        $name = $trimmed.Substring(0, $idx).Trim()
        $value = $trimmed.Substring($idx + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if (-not [string]::IsNullOrWhiteSpace($name) -and -not [System.Environment]::GetEnvironmentVariable($name, "Process")) {
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Redact-ProbeText {
    param(
        [AllowNull()][string]$Text,
        [AllowNull()][string]$Secret
    )
    if ($null -eq $Text) {
        return $null
    }
    $safe = $Text
    if (-not [string]::IsNullOrEmpty($Secret)) {
        $safe = $safe.Replace($Secret, "<redacted>")
    }
    $safe = [regex]::Replace($safe, "data:image/[^;]+;base64,[A-Za-z0-9+/=]+", "data:image/<base64-redacted>")
    return $safe
}

function Read-ResponseBody {
    param($Response)
    if ($null -eq $Response) {
        return $null
    }
    $stream = $Response.GetResponseStream()
    if ($null -eq $stream) {
        return $null
    }
    $reader = New-Object System.IO.StreamReader($stream)
    try {
        return $reader.ReadToEnd()
    }
    finally {
        $reader.Dispose()
    }
}

function Invoke-SiliconFlowJson {
    param(
        [ValidateSet("GET", "POST")][string]$Method,
        [string]$Uri,
        [AllowNull()][object]$Body,
        [string]$ApiKey,
        [int]$TimeoutSec = 120
    )

    $headers = @{
        "Authorization" = "Bearer $ApiKey"
        "Accept" = "application/json"
    }
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        if ($Method -eq "GET") {
            $response = Invoke-WebRequest -UseBasicParsing -Method GET -Uri $Uri -Headers $headers -TimeoutSec $TimeoutSec
        }
        else {
            $jsonBody = $Body | ConvertTo-Json -Depth 30 -Compress
            $response = Invoke-WebRequest -UseBasicParsing -Method POST -Uri $Uri -Headers $headers -ContentType "application/json; charset=utf-8" -Body $jsonBody -TimeoutSec $TimeoutSec
        }
        $sw.Stop()
        return [ordered]@{
            ok = $true
            status_code = [int]$response.StatusCode
            latency_ms = [int]$sw.ElapsedMilliseconds
            trace_id = [string]$response.Headers["x-siliconcloud-trace-id"]
            body_text = Redact-ProbeText -Text ([string]$response.Content) -Secret $ApiKey
        }
    }
    catch {
        $sw.Stop()
        $statusCode = $null
        $bodyText = $null
        if ($_.Exception.Response) {
            try {
                $statusCode = [int]$_.Exception.Response.StatusCode
                $bodyText = Read-ResponseBody -Response $_.Exception.Response
            }
            catch {
                $bodyText = $null
            }
        }
        return [ordered]@{
            ok = $false
            status_code = $statusCode
            latency_ms = [int]$sw.ElapsedMilliseconds
            trace_id = $null
            error_class = $_.Exception.GetType().FullName
            error_message = Redact-ProbeText -Text ([string]$_.Exception.Message) -Secret $ApiKey
            body_text = Redact-ProbeText -Text $bodyText -Secret $ApiKey
        }
    }
}

function ConvertFrom-JsonOrNull {
    param([AllowNull()][string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $null
    }
    try {
        return $Text | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Get-ApiErrorInfo {
    param([hashtable]$Response)
    $parsed = ConvertFrom-JsonOrNull -Text $Response.body_text
    if ($null -eq $parsed) {
        return [ordered]@{
            code = $null
            message = $Response.error_message
            type = $Response.error_class
        }
    }
    if ($parsed.error) {
        return [ordered]@{
            code = $parsed.error.code
            message = $parsed.error.message
            type = $parsed.error.type
        }
    }
    return [ordered]@{
        code = $parsed.code
        message = $parsed.message
        type = $parsed.type
    }
}

function Get-ContentHash {
    param([AllowNull()][string]$Text)
    if ($null -eq $Text) {
        return $null
    }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Extract-JsonCandidate {
    param([AllowNull()][string]$Content)
    if ([string]::IsNullOrWhiteSpace($Content)) {
        return [ordered]@{ valid = $false; source = "empty"; parsed = $null; error = "empty content" }
    }
    $matches = [regex]::Matches($Content, '```json\s*([\s\S]*?)```', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($match in $matches) {
        [void]$candidates.Add($match.Groups[1].Value.Trim())
    }
    $firstBrace = $Content.IndexOf('{')
    $lastBrace = $Content.LastIndexOf('}')
    if ($firstBrace -ge 0 -and $lastBrace -gt $firstBrace) {
        [void]$candidates.Add($Content.Substring($firstBrace, $lastBrace - $firstBrace + 1).Trim())
    }
    foreach ($candidate in $candidates) {
        try {
            $parsed = $candidate | ConvertFrom-Json
            $hasText = $null -ne $parsed.text
            $hasTables = $null -ne $parsed.tables
            $hasWarnings = $null -ne $parsed.warnings
            return [ordered]@{
                valid = $true
                source = "content_candidate"
                has_required_fields = ($hasText -and $hasTables -and $hasWarnings)
                parsed = $parsed
                error = $null
            }
        }
        catch {
            continue
        }
    }
    return [ordered]@{ valid = $false; source = "not_found"; parsed = $null; error = "No valid JSON object found in assistant content" }
}

function Summarize-ChatResponse {
    param(
        [string]$Label,
        [string]$InputKind,
        [string]$Model,
        [hashtable]$Response
    )

    $parsed = ConvertFrom-JsonOrNull -Text $Response.body_text
    $content = $null
    $finishReason = $null
    $usage = $null
    $responseModel = $null
    $markdownLikely = $false
    $jsonCheck = [ordered]@{ valid = $false; source = "no_200_response"; parsed = $null; error = "No successful response" }

    if ($Response.ok -and $null -ne $parsed) {
        $responseModel = $parsed.model
        $usage = $parsed.usage
        if ($parsed.choices -and $parsed.choices.Count -gt 0) {
            $choice = $parsed.choices[0]
            $finishReason = $choice.finish_reason
            $content = [string]$choice.message.content
            if ($content -match '\|' -or $content -match '```' -or $content -match '^#') {
                $markdownLikely = $true
            }
            $jsonCheck = Extract-JsonCandidate -Content $content
        }
    }

    $errorInfo = $null
    if (-not $Response.ok) {
        $errorInfo = Get-ApiErrorInfo -Response $Response
    }

    return [ordered]@{
        label = $Label
        input_kind = $InputKind
        request_model = $Model
        ok = $Response.ok
        status_code = $Response.status_code
        latency_ms = $Response.latency_ms
        trace_id_present = -not [string]::IsNullOrWhiteSpace($Response.trace_id)
        response_model = $responseModel
        finish_reason = $finishReason
        usage = $usage
        returns_markdown_like_content = $markdownLikely
        json_instruction = [ordered]@{
            valid_json_found = $jsonCheck.valid
            has_required_fields = $jsonCheck.has_required_fields
            error = $jsonCheck.error
        }
        content_sha256 = Get-ContentHash -Text $content
        content_excerpt = if ($content) { $content.Substring(0, [Math]::Min(900, $content.Length)) } else { $null }
        error = $errorInfo
    }
}

function New-ChatBody {
    param(
        [string]$Model,
        [string]$ImageUrl,
        [string]$Prompt
    )
    return [ordered]@{
        model = $Model
        messages = @(
            [ordered]@{
                role = "user"
                content = @(
                    [ordered]@{
                        type = "image_url"
                        image_url = [ordered]@{
                            url = $ImageUrl
                            detail = "high"
                        }
                    },
                    [ordered]@{
                        type = "text"
                        text = $Prompt
                    }
                )
            }
        )
        stream = $false
        temperature = 0
        max_tokens = 1600
    }
}

function Is-ModelUnavailableError {
    param([hashtable]$Response)
    if ($Response.ok) {
        return $false
    }
    $err = Get-ApiErrorInfo -Response $Response
    $joined = (($err.code, $err.message, $err.type) -join " ").ToLowerInvariant()
    return ($joined -match "model_not_found" -or $joined -match "not.?found" -or $joined -match "unavailable" -or $joined -match "offline" -or $Response.status_code -eq 404)
}

function Try-NewPublicImageUrl {
    param([string]$Path)
    if (-not [string]::IsNullOrWhiteSpace($env:SILICONFLOW_PROBE_IMAGE_URL)) {
        return [ordered]@{
            ok = $true
            source = "env:SILICONFLOW_PROBE_IMAGE_URL"
            url = $env:SILICONFLOW_PROBE_IMAGE_URL
            error = $null
        }
    }
    if ($env:SILICONFLOW_PROBE_SKIP_UPLOAD -eq "1") {
        return [ordered]@{ ok = $false; source = "skipped"; url = $null; error = "SILICONFLOW_PROBE_SKIP_UPLOAD=1" }
    }
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($null -eq $curl) {
        return [ordered]@{ ok = $false; source = "0x0.st"; url = $null; error = "curl.exe not available" }
    }
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $url = (& curl.exe -fsS -F "file=@$Path" https://0x0.st).Trim()
        $sw.Stop()
        if ($url -match "^https?://") {
            return [ordered]@{
                ok = $true
                source = "0x0.st"
                url = $url
                upload_latency_ms = [int]$sw.ElapsedMilliseconds
                error = $null
            }
        }
        return [ordered]@{ ok = $false; source = "0x0.st"; url = $null; error = "Unexpected upload response" }
    }
    catch {
        return [ordered]@{ ok = $false; source = "0x0.st"; url = $null; error = $_.Exception.Message }
    }
}

Load-DotEnv -Path $envPath

$apiKey = $env:SILICONFLOW_API_KEY
$baseUrl = if ($env:SILICONFLOW_API_BASE_URL) { $env:SILICONFLOW_API_BASE_URL.TrimEnd("/") } else { "https://api.siliconflow.cn/v1" }
$primaryModel = if ($env:SILICONFLOW_PADDLEOCR_VL_PRIMARY_MODEL) { $env:SILICONFLOW_PADDLEOCR_VL_PRIMARY_MODEL } else { "PaddlePaddle/PaddleOCR-VL-1.5" }
$fallbackModel = if ($env:SILICONFLOW_PADDLEOCR_VL_FALLBACK_MODEL) { $env:SILICONFLOW_PADDLEOCR_VL_FALLBACK_MODEL } else { "PaddlePaddle/PaddleOCR-VL" }
$testedModelIds = @($primaryModel, $fallbackModel)
$prompt = "Распознай документ. Верни Markdown и затем JSON с полями: text, tables, warnings. Не добавляй факты, которых нет на изображении."

if ([string]::IsNullOrWhiteSpace($apiKey)) {
    $blocked = [ordered]@{
        status = "blocked"
        blocker = "missing_siliconflow_api_key"
        message = "SILICONFLOW_API_KEY is empty in the process environment and .env."
        secrets_printed = $false
        generated_at = (Get-Date).ToString("o")
    }
    $blocked | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $resultPath -Encoding UTF8
    Write-Output "PROBE_STATUS=blocked"
    Write-Output "PROBE_RESULT=$resultPath"
    exit 2
}

if (-not (Test-Path -LiteralPath $imagePath)) {
    throw "Synthetic image is missing: $imagePath"
}

$modelsResponse = Invoke-SiliconFlowJson -Method GET -Uri "$baseUrl/models" -Body $null -ApiKey $apiKey -TimeoutSec 60
$modelsParsed = ConvertFrom-JsonOrNull -Text $modelsResponse.body_text
$modelIds = @()
if ($modelsParsed -and $modelsParsed.data) {
    $modelIds = @($modelsParsed.data | ForEach-Object { $_.id } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}
$modelsSummary = [ordered]@{
    endpoint = "GET /models"
    ok = $modelsResponse.ok
    status_code = $modelsResponse.status_code
    latency_ms = $modelsResponse.latency_ms
    object = if ($modelsParsed) { $modelsParsed.object } else { $null }
    model_count = $modelIds.Count
    tested_ids = @(
        foreach ($id in $testedModelIds) {
            [ordered]@{ id = $id; listed = ($modelIds -contains $id) }
        }
    )
    matching_model_ids = @($modelIds | Where-Object { $testedModelIds -contains $_ })
    error = if ($modelsResponse.ok) { $null } else { Get-ApiErrorInfo -Response $modelsResponse }
}
$modelsSummary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $probeDir "models_summary.safe.json") -Encoding UTF8

$imageBytes = [System.IO.File]::ReadAllBytes($imagePath)
$imageB64 = [System.Convert]::ToBase64String($imageBytes)
$dataImageUrl = "data:image/png;base64,$imageB64"

$chatSummaries = New-Object System.Collections.Generic.List[object]
$rawSafeResponses = [ordered]@{}

$primaryBody = New-ChatBody -Model $primaryModel -ImageUrl $dataImageUrl -Prompt $prompt
$primaryResponse = Invoke-SiliconFlowJson -Method POST -Uri "$baseUrl/chat/completions" -Body $primaryBody -ApiKey $apiKey -TimeoutSec 180
$rawSafeResponses["base64_primary"] = [ordered]@{
    status_code = $primaryResponse.status_code
    latency_ms = $primaryResponse.latency_ms
    trace_id_present = -not [string]::IsNullOrWhiteSpace($primaryResponse.trace_id)
    body = ConvertFrom-JsonOrNull -Text $primaryResponse.body_text
}
[void]$chatSummaries.Add((Summarize-ChatResponse -Label "base64_primary" -InputKind "data_image_base64" -Model $primaryModel -Response $primaryResponse))

$workingModel = $null
$base64Working = $false
$fallbackResponse = $null
if ($primaryResponse.ok) {
    $workingModel = $primaryModel
    $base64Working = $true
}
elseif (Is-ModelUnavailableError -Response $primaryResponse) {
    $fallbackBody = New-ChatBody -Model $fallbackModel -ImageUrl $dataImageUrl -Prompt $prompt
    $fallbackResponse = Invoke-SiliconFlowJson -Method POST -Uri "$baseUrl/chat/completions" -Body $fallbackBody -ApiKey $apiKey -TimeoutSec 180
    $rawSafeResponses["base64_fallback"] = [ordered]@{
        status_code = $fallbackResponse.status_code
        latency_ms = $fallbackResponse.latency_ms
        trace_id_present = -not [string]::IsNullOrWhiteSpace($fallbackResponse.trace_id)
        body = ConvertFrom-JsonOrNull -Text $fallbackResponse.body_text
    }
    [void]$chatSummaries.Add((Summarize-ChatResponse -Label "base64_fallback_after_primary_unavailable" -InputKind "data_image_base64" -Model $fallbackModel -Response $fallbackResponse))
    if ($fallbackResponse.ok) {
        $workingModel = $fallbackModel
        $base64Working = $true
    }
}

$urlProbe = [ordered]@{ attempted = $false; upload = $null; chat = $null }
if ($workingModel) {
    $upload = Try-NewPublicImageUrl -Path $imagePath
    $urlProbe.upload = $upload
    if ($upload.ok) {
        $urlProbe.attempted = $true
        $urlBody = New-ChatBody -Model $workingModel -ImageUrl $upload.url -Prompt $prompt
        $urlResponse = Invoke-SiliconFlowJson -Method POST -Uri "$baseUrl/chat/completions" -Body $urlBody -ApiKey $apiKey -TimeoutSec 180
        $urlSummary = Summarize-ChatResponse -Label "public_url_working_model" -InputKind "public_image_url" -Model $workingModel -Response $urlResponse
        $urlProbe.chat = $urlSummary
        [void]$chatSummaries.Add($urlSummary)
        $rawSafeResponses["public_url"] = [ordered]@{
            status_code = $urlResponse.status_code
            latency_ms = $urlResponse.latency_ms
            trace_id_present = -not [string]::IsNullOrWhiteSpace($urlResponse.trace_id)
            body = ConvertFrom-JsonOrNull -Text $urlResponse.body_text
        }
    }
}

$rawSafeResponses | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath (Join-Path $probeDir "chat_responses.safe.json") -Encoding UTF8

$normalizable = $false
foreach ($summary in $chatSummaries) {
    if ($summary.ok -and $summary.json_instruction.valid_json_found -and $summary.json_instruction.has_required_fields) {
        $normalizable = $true
    }
}

$result = [ordered]@{
    status = if ($base64Working) { "complete" } else { "blocked" }
    generated_at = (Get-Date).ToString("o")
    secrets_printed = $false
    synthetic_image = [ordered]@{
        path = "docs/reports/2026-06-25/siliconflow-paddleocr-vl-probe/synthetic_test_document.png"
        bytes = $imageBytes.Length
        sha256 = (Get-FileHash -LiteralPath $imagePath -Algorithm SHA256).Hash.ToLowerInvariant()
        contains_customer_data = $false
    }
    official_tested_endpoint = "$baseUrl/chat/completions"
    models_endpoint = $modelsSummary
    tested_model_ids = $testedModelIds
    working_model_id = $workingModel
    base64_accepted = $base64Working
    public_url = $urlProbe
    chat_summaries = $chatSummaries
    can_normalize_to_document_extraction_result_v1 = $normalizable
    cost_usage = [ordered]@{
        pricing_page_signal = "SiliconFlow pricing page lists PaddlePaddle/PaddleOCR-VL-1.5 as free input and free output."
        api_usage_present = @($chatSummaries | Where-Object { $null -ne $_.usage }).Count -gt 0
        actual_deduction_observed_via_api = "not_available_in_chat_or_models_response"
    }
}

$result | ConvertTo-Json -Depth 60 | Set-Content -LiteralPath $resultPath -Encoding UTF8

Write-Output ("PROBE_STATUS=" + $result.status)
Write-Output ("MODELS_STATUS=" + $modelsSummary.status_code)
Write-Output ("WORKING_MODEL_ID=" + $(if ($workingModel) { $workingModel } else { "none" }))
Write-Output ("BASE64_ACCEPTED=" + $base64Working)
Write-Output ("PUBLIC_URL_ATTEMPTED=" + $urlProbe.attempted)
Write-Output ("RESULT_PATH=" + $resultPath)
