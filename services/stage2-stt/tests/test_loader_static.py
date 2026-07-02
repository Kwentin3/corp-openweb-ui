from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
LOADER_PATH = ROOT / "deploy" / "openwebui-static" / "loader.js"


def test_loader_binds_postprocessing_actions_to_prepared_file_scope():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("async function runTranscription")
    end = source.index("async function callTranscriptionAction", start)
    run_transcription = source[start:end]

    assert "const preparedFile = isPreparedStage2Audio(file) ? file : await prepareMediaFile(file, status);" in run_transcription
    assert "const content = await callTranscriptionAction(preparedFile, status);" in run_transcription
    assert "loadPostprocessingActions(preparedFile, transcriptRef, button.parentElement, status)" in run_transcription
    assert "loadPostprocessingActions(file, transcriptRef, button.parentElement, status)" not in run_transcription
