from __future__ import annotations

import base64
import copy
import hashlib
import json
import zlib
from typing import Any


SEMANTIC_MODEL_ASSET_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_model_assets_v1"
)
PACK_ID = "broker_reports_managed_financial_semantic_pack"
PACK_SEMANTIC_VERSION = "1.0.0"
PACK_GIT_BLOB_SHA256 = (
    "ae07f1d378169e82792aa1f0ed6cebc346591e047656f14df0fcead1f5a18d1f"
)
PACK_INTEGRITY_SHA256 = (
    "ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8"
)
PACK_CANONICAL_SEMANTIC_BYTES = 9404
MANAGED_PROMPT_GIT_BLOB_SHA256 = (
    "3f169c79a9bf6f0eb1b476853ed1ace50cca9b2f7fd2d2fe3394f2ab3f6d5a2e"
)
MANAGED_ASSET_IDENTITIES_SHA256 = (
    "a8de2b91f4cbde77bc2215ffb85b726e7b963dc77d6eb1a86e0b3e80499509a4"
)
MANAGED_PROMPT_INPUT_MARKER = (
    "{{financial_semantic_matching_input_json}}"
)
FACTORY_REQUIRED = (
    "load_gate2_financial_semantic_model_assets is the only closed-world "
    "managed financial model-asset projection entrypoint"
)
FORBIDDEN = (
    "The projection must not read runtime files, use network or RAG, omit "
    "Pack semantic entries, expose repository paths, or reinterpret meaning"
)

_PACK_PAYLOAD_B85 = (
    b"c-rk+-HzMF6~6aV5W3!7NYo$YTx~b5Yc$<8*6RXA5fH<fp)@uBLJoJW7zUc8KrRCGS%Ne!(gJp0LHkBMXJ$waDM~"
    b"B5cAFwL?DdLs=FFM%e?IZWJ;xaobj4%hU-P^WX)?I)41zp;#&bXCS(?kj4@E)}DoErPK$u8D{fy9O{`F{ZgbdUN!"
    b"FqNAHCb}Di-X=?Ke8kkoeWQgdb#33ih@hv9O8PK@#KaFrMO?SKCbv2BkTJX2bv~D8G~5xi_8g?d+xd|F-v125^Jx"
    b"yH7VsP&4pb1g(R{pkeMX;5`;|BJSI|HbNEgA5&WXJ<R!=#b064<Yamb(gd{4sRzzCnl=}fGcq9@IYcJq2?&C{Q$b"
    b"7v=?j@1jwWQ|Pg7E~nHG8$(HoIa)-02Lt4Ff`_3qqJXT?7k08j<O6JP(5TI2bNw6PLQgn}^H=GBTb89-pvaPN!_j"
    b"y{Sv6SFt9P@=SvM<T~Tv6R4FxswK1oDOPa1h@f0WLb76&%0@2qq+BGjrTv)899?5HP&A*La~KbKo&zN%2@?!1zjY"
    b"X_3Q&Gp6h4Wf^hTW;r`J5@N&D1((p~}i7bRMJ?<FD*1_Y~<Kt#$tb`xb}t)#&aWMu@GkUZ|8%f)gf{WSDT_@D!!U"
    b"w>pxf{5>zFXxnl`yD{HEF&W8(A!H~a9XNh5Xm*%D9!to)G}hkmxQkUYz={wSWyI=a@0x{F0okVDq4IKAsAIA)aoc"
    b"i)-QFqlO#<9Rmmm?9}-_yp=QDf;v!`tS>jnwuYP@8dvB1&c0j_DH24#Tn19CCews6$<Ccg&7c>QtvX!8<<L5cCXt"
    b"JEc;n$$MCKu>MLw~aZQx}k_Fw6%aFt1it7$qcH;;mLF&)~^#PLDB84FQJ8Qt3JrJYs$t3kg<2%4W%gcCD1Kj3UTk"
    b"afT_ZvPc~-FDf&NBr9bVyvi1L#;g=FQkOUbQpb=w^$|54gsez}vBcoi(Y8EBvvcO)Ima{tPpeskY3`83;m@;3P$3"
    b";fiQ(cD6!Jf;F-NCAu%&}J;KaG)1?CIn2)heV245=vhH2rDoC8Z5l?<MiNyOnqx#C8g`m|{6C}{-fSP{eyDS#*V4"
    b"awI^+!NdTO$k$b@P0~ID~v_R>6%7OQrG)xpI0TJ*`Upwr>vylL!wg?YmI`NQ5B(zA^{s)%Q=@K-?^4W;Cm|hbZw5"
    b"LhVo^TBhhuFz@%Y<FeEYLH*P0gXR9nJ?}rG)il8!1mZum|7|hqL%QRhpC`yRkC|#-;*4wJoQ6~?)LmH{mU)a}z{G"
    b"6*;Xk>CMih84QZxW}FWGp!p!8M6Wt~8=dsqf1;6>yg>EhWk)Fw?8XB;j2OvmZJa-;z(}CAa8a9vvocfmMLnzO`58"
    b"9>V{wz;)32DrgUqI>+LU&C7=pz5e}k%K_62y%G$3sP9x+QOEot7nA(CyyH$^@;rq~;eTMW=n_lU2Z_Cl_<tk1;T4"
    b"g9NB?J9FQNV&Byu0&`xd!32%zQ$g2Cj_iGl&gu5LS@3^Hi3Qs(o7^*)F2&*h*wYOAiO*4+>rVKG~@b6s<drXCreR"
    b"I2LktQSE)_PVv-=%^6O#LrSF`D?pv^R4A(4^C7Po2#nwSaq*AG4IKKo$Rqy+=?~ygzLC-N~`~<dK#On{aiIHVW&m"
    b"1i8nuPUTt2(zrSx@-+s4w<=lRC`)Bz0BmDpM=7-Jq4y?kDH@9Eke!F=E&tBhtbNg2Z_I(eJzS)+VKPPdvr5ot=)("
    b"NywP~EL2E>CalZc8l`*zomUQg?%$%cvHx(-xj=OGUB9Lq)k$I25Up!)_kUBm_f^qeda;23qs9l-tr)JtI{k$BC_N"
    b"`ylAt(gIpq6;;5V0++(6hEoToofXfa>jeJzw>Snn8bx$@>b6x4&L}nXUxYa_l_YX*R%yZe<Z?vezzkKZzei_vJH|"
    b"u-`c@rVTXS}r8;~UtNg;I%?VjOVDIzcR-0&2Hlq(Pklc19(;0!k_-qEa?4U~19O1P?<*SGitu5S*n6kyB*ij-XyK"
    b"(;`Utvy;yoEyrd?)}+GlfA4gzw7d9T&nEYf8Eo@&O-USb^>??7Kd^76H6IFIik8V+yGL2ci?#|;ofGTZ;9MYRYy+"
    b"E<ft=YDW2LQ=v(c$*gI$yWDS;0?aOTWBZ&jCRM-prWGd~o!uV{JqO;qU>v$1jXJrBM@0bwvEQTsaCY<E0NZZN3ZI"
    b"GjGI#ODy>XG&>h<i#B)KS2l0CE$$E9e78z)Cq#x{FSrt00KPGw!I)#~~5A14s+jEkkf?foIl<sWV>dIj6~&4#Jtx"
    b"7xhGboH8ESTCVP{B2%Z~HuJtft<p9M)SBY&)R$3#>Whw)#9j5BIOiOrMI<mMz!S@)k$^(az)h^-9Jp%uh(tAt+nF"
    b"0<kimkAa7qnD)Qf?1Nn0_4-5jEkckr;N+S`p)>?t`f`*~EP&1Bp(RTlUgcFJ8rLVQfQ$mIRd^JZ?aAns^5Azm;Eh"
    b"hE@Lf*B9^a2C?JH=%s)1%W%Cx)bg)Hk)&gQoe9`7>>eetJTqr(YW`2b$RjI2bcckgU1(_S5N$hr&kYL|LpYq;{4I"
    b"s>1Y0@7r#4wbnZXAIQ?wopPpSkg=c3Mmye%5f&b3W9z4GCAD#dH!THt2<sY{F6RNZ9xtMx<C@2m!0ODua*D7e3Lz"
    b"p((@)3hpHsE<xA%Xvr=c<aJm1fgXIGaxAbC=Iuk9vzK^TNf1jomODPk2B^jE*>;j~4FO9WOi<1d~ZPn-e|?$Z+V{"
    b"N`-!ufvt)H8rc?1qb_eZ?nb(pWEqH~m+#rh)Og2kr0<Zr-GF_MP0_5WP5Io7_cfHdI72X-idz-nU~LzOF8tRdjt2"
    b"fyO(4+e0pi4YB<s3f^({`Ar!m%8Y~Ge8+e4;`s4io8>O*|w?#1)!tsgPHkC@*3MFpzBQ+3_`;x7Dopk=>!pzr;It"
    b"{+jpJA*=H^n(QNC;bRc{&K*{s+wa3f}Ud4@dj1sKorPL&qTuB5sp+#aHsa_&lr+CsIKgTDEl!@6K)40mS$4Sw%SG"
    b"21P<Em3$z#eT1p_g{mbSj1SL1GZ@=2S+5B+(-R2+8=BL}Q;ltmK6kfUc*XGsjw}?<8nL;*!<OifeSo006y#^-#+`"
    b"RhF@XH!<Q~Hf+(5c(EYJI&Qs8XNM*SzXBm###_5XS7H2cTT8Ht0?aKcinIQiEY>s5@^G^ST>1ZMe2Un_Yr<4&J&!"
    b"7Btq_?a@0p$9u&Y?|d_%gSxe$L4$yjHppyXs<%ZR-wuY;Q)y#Fe|xrQiGEeXfmJR*uhZA)9i0#eRhhfrQ}F5vKdE"
    b"uXx09c7NkmlTBXG7|8rOshRj<|E0bBRtg2qJ)2cn3yBCUaHl^Q+_a)?4z;%dxoCu~<G*TW#ggbRi56Ft8s^#H3bg"
    b"sSMg=>q3kF=QR_X{yw!fiQ(~6BFT}J|1T)QsA71d_e|TnWBS}zat2^d!TRGuy3~4sG!lJ(rp*_>tvFn&Zxg17%Yq"
    b"G`y%7=Rvgs9_C689s?-|9<Q*}>4wrXC2|HXq;)Fj_oNzw%C~-Mq;fQ#y>rL6nV{FVvV?G&^x#vx00dq%mu~^JT?r"
    b"cnkluZJ@prgrnwD86s3Mag0?g^R#eMld_n2N}{X-Umnl<)l7c!zKEUUGw+RSBfx4(?n}?adp&q>Q8w%z{YG5cYeU"
    b"fquIdPE)T_b|#JL<xV3(_XYGF<m%O6eC2pWz>uw%jY+vwEp(kQo9e@u54VAIfCPwr;V{*D4YnR@`Zz-(7U5dG6Yg"
    b"7x>QUdio&kE7syV@ayBEKP)T>ISMr8eVIu3eYKqXOyt4qQV`+IJNtrS9J-M&+%U`~~q3=jRaYtPK5-%s6oa}{xyU"
    b">HmZ{FzYZjmBdVxHC3qlzV(S9L?uL>ax)!bm<5J#T`y*K-f4WE}iiqpNHPy-phOc27j6pTm"
)
_PROMPT_PAYLOAD_B85 = (
    b"c-nnb+j8145PkPo><1VZoDlMwnNHK`C1pbUY_FxYtsqOTBtvK>|K63sA=9+wfx&op&z_6)6}JS|5L9+Bk|f+>Ajs"
    b"i^GH8TC4exD-%0P!fw8}IfNhq(Z$&%!z@AZMZ`75-<B?cQF@uqjPRaz%y<?NQ+%u#P$@Uwa<o5`_kHbIoIBNri{T"
    b"x9cXUS{ycq8u@V?Rrgtk~7GL7&s^aYZTjQ8)t{6eZAELU!35J7x==T1{6IH$TUO!>tzYwt<``=CXRj%%Fz*YD*AJ"
    b"A*sIWjGJzVW!T~lPZ)W-ODk-s=S4-s2rI6Q)iwmssE4h+_u4y@6tX6Z8%f)4#i$x{#e7+PF%8MFvaYb`l)z>Af|H"
    b"IQraNk;e_RrhFiKr8UJ_e{r+kFP#+jE67{Sd(JjRzmxAj05KC!|%QDy8F^%nwj=BUd{f{?1Vym9JQp!1Vla;7A>H"
    b"OwTy&MYN<NG;CzX0RUqI47_SXh8PI8#_l!AhElk{xlQ5o`I)+kq~u1QvXUZLmv}-a+7#A@(6X+*BdG*Olq(!H^q7"
    b"KmM-{A#onUKzR36rjlM(<uv$0&@l9%<)cHzKNqcbe$J+TmGJPRy~65&l^8ph3EMT2%qk`Yu)N21s*O8B(-b_ce4;"
    b"QdD-BRVg}0(;6JnnsT(!gz2fu3LsfPqG+oDN`s1BQ$!iYDKSuczU0d#=iYGs=$qY=;Nv+`N*u<G-mz(aU34Dg;RU"
    b"V&CCZTDbH5I4)s7RqN4;k0L@?rKMwcgb|)@V=%!j`-IME7h@*H7Znzskl-ZF9X(CXIK{HYc*feb9_%k>(zP7GQSv"
    b"1$7R=+6P+@o?M!<w%V=oFKQ_YekT+n%2Oa#p9C<jAsk@YXy(C%*xfg35d"
)
_IDENTITIES_PAYLOAD_B85 = (
    b"c-oDWTaViy5QYDW#dEv@Y<$UMRkcr5tG-qh8em9JV&h_*YPH(`USj9gbkp_`!JHY+`QU|E=-mEUIz!e(1;4`}0}e"
    b"jKQEnh2m)7;rYX^I2d<U+VFpd~UvLYSy&f*y5xCJh%qX0L|2xdjomXz_PW~QxZp+u`Vl*Wj*)~#v^(4}Fju34!pq"
    b"qMA=nm6fG5*>o?hDg>g1O}JJ!alnAd|YearH(gq-p|)T)LVIANyXr(gBzmreLDZS$4vRDH)ygipm#Y;aqEMN5ZwW"
    b"@xz6>Q%nuk~u33>AL-La$`P?wSG|bP1`P|cu67*4!tYerk`GXOTgZn8CQ*udfu>*O)FfL>L!)`nrZ?91r)b3caTy"
    b"0F^I!*zNJP8N<F}bu}`o6A64_z99yqop2uZw>6G3jSK`*3cMeLCNJ);-O&kieek6D3J%4*S38IGZ6)39iV-MXB~)"
    b"UHK?1t6E*R&?;M5ii)YSt{PFGVW3e^t<x5_wKd#ui$&3vmV+v6Wdv|cqB}PukfQ2;qMF>b-I&}>u;?3yFV}dum$r"
    b"6pzkiFj-x->@@%{ceOR;Xf$*d0-s7}^i%(x)+0HiBI%bUt?&p*N_!e%7vZ+BX$;$Cfeny^Vke1Ay86@&M4(S?S;r"
    b"~b!pu-Nxj*tCI?3SG6TssJ>%S~E0MVIc&F7P+wva+UrGt82q(3SDtt7MwOnxe;%LeeU)+>(^g?jH+("
)


def load_gate2_financial_semantic_model_assets() -> dict[str, Any]:
    """Return exact managed identities, Prompt, and complete compact Pack."""

    pack = _verified_pack()
    prompt_content = _verified_prompt()
    managed_assets = _verified_identities()
    return {
        "schema_version": SEMANTIC_MODEL_ASSET_SCHEMA_VERSION,
        "semantic_pack": {
            "schema_version": pack["schema_version"],
            "pack_id": pack["pack_id"],
            "semantic_version": pack["semantic_version"],
            "managed_asset_ref": pack["managed_asset_ref"],
            "consumer_contract_version": pack[
                "consumer_contract_version"
            ],
            "integrity_sha256": pack["integrity_sha256"],
            "full_compact_snapshot": copy.deepcopy(
                pack["full_compact_snapshot"]
            ),
        },
        "managed_assets": copy.deepcopy(managed_assets),
        "prompt_content": prompt_content,
        "prompt_ref": (
            "openwebui:"
            + managed_assets["prompt"]["api_identity"]["id"]
            + "@"
            + managed_assets["prompt"]["api_identity"]["version_id"]
        ),
        "prompt_git_blob_sha256": MANAGED_PROMPT_GIT_BLOB_SHA256,
    }


def _verified_pack() -> dict[str, Any]:
    raw = _decompress(_PACK_PAYLOAD_B85, "financial_semantic_pack")
    if hashlib.sha256(raw).hexdigest() != PACK_GIT_BLOB_SHA256:
        raise RuntimeError("financial_semantic_pack_blob_hash_mismatch")
    try:
        payload: Any = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("financial_semantic_pack_json_invalid") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("pack_id") != PACK_ID
        or payload.get("semantic_version") != PACK_SEMANTIC_VERSION
        or payload.get("runtime_activation") is not False
        or not isinstance(payload.get("full_compact_snapshot"), list)
        or not payload["full_compact_snapshot"]
    ):
        raise RuntimeError("financial_semantic_pack_identity_mismatch")
    material = copy.deepcopy(payload)
    supplied_integrity = material.pop("integrity_sha256", None)
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if (
        len(canonical) != PACK_CANONICAL_SEMANTIC_BYTES
        or hashlib.sha256(canonical).hexdigest()
        != PACK_INTEGRITY_SHA256
        or supplied_integrity != PACK_INTEGRITY_SHA256
    ):
        raise RuntimeError("financial_semantic_pack_integrity_mismatch")
    return payload


def _verified_prompt() -> str:
    raw = _decompress(
        _PROMPT_PAYLOAD_B85,
        "financial_semantic_prompt",
    )
    if hashlib.sha256(raw).hexdigest() != MANAGED_PROMPT_GIT_BLOB_SHA256:
        raise RuntimeError("financial_semantic_prompt_hash_mismatch")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError("financial_semantic_prompt_utf8_invalid") from exc
    if content.count(MANAGED_PROMPT_INPUT_MARKER) != 1:
        raise RuntimeError("financial_semantic_prompt_marker_invalid")
    return content


def _verified_identities() -> dict[str, Any]:
    raw = _decompress(
        _IDENTITIES_PAYLOAD_B85,
        "financial_semantic_asset_identities",
    )
    if hashlib.sha256(raw).hexdigest() != MANAGED_ASSET_IDENTITIES_SHA256:
        raise RuntimeError("financial_semantic_asset_identities_hash_mismatch")
    try:
        identities: Any = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "financial_semantic_asset_identities_json_invalid"
        ) from exc
    if (
        not isinstance(identities, dict)
        or set(identities) != {
            "family_id",
            "manifest_sha256",
            "semantic_version",
            "skill",
            "prompt",
        }
        or identities.get("family_id")
        != "broker_reports_gate2_financial_domain_assets"
        or identities.get("semantic_version") != "1.0.0"
        or identities.get("prompt", {}).get("git_blob_sha256")
        != MANAGED_PROMPT_GIT_BLOB_SHA256
        or identities.get("skill", {}).get("asset_id")
        != "broker_reports_financial_domain_skill"
        or identities.get("prompt", {}).get("asset_id")
        != "broker_reports_gate2_financial_matching_prompt"
    ):
        raise RuntimeError("financial_semantic_asset_identities_invalid")
    return identities


def _decompress(payload: bytes, label: str) -> bytes:
    try:
        return zlib.decompress(base64.b85decode(payload))
    except Exception as exc:
        raise RuntimeError(label + "_payload_invalid") from exc
