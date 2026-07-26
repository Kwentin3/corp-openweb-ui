"""
title: Broker Reports Financial Semantic Pack
author: Corp OpenWebUI
version: 1.0.0
required_open_webui_version: 0.9.6
"""

from __future__ import annotations

import base64
import hashlib
import json
import zlib
from typing import Any


PACK_ID = "broker_reports_managed_financial_semantic_pack"
PACK_SEMANTIC_VERSION = "1.0.0"
PACK_GIT_BLOB_SHA256 = (
    "ae07f1d378169e82792aa1f0ed6cebc346591e047656f14df0fcead1f5a18d1f"
)
PACK_INTEGRITY_SHA256 = (
    "ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8"
)
PACK_CANONICAL_SEMANTIC_BYTES = 9404
FACTORY_REQUIRED = (
    "Tools.load_financial_semantic_pack is the only managed OpenWebUI Pack "
    "delivery entrypoint"
)
FORBIDDEN = (
    "The Tool must not read a runtime filesystem path, use network or RAG, "
    "return a partial Pack, or reinterpret financial semantics"
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


class Tools:
    """Expose the exact versioned Financial Semantic Pack to OpenWebUI."""

    def __init__(self) -> None:
        self._pack_json = _verified_pack_json()

    def load_financial_semantic_pack(self) -> str:
        """Return the complete pinned Financial Semantic Pack JSON.

        :return: Exact UTF-8 repository Git-blob Pack content.
        """

        return self._pack_json


def _verified_pack_json() -> str:
    try:
        raw = zlib.decompress(base64.b85decode(_PACK_PAYLOAD_B85))
    except Exception as exc:
        raise RuntimeError("financial_semantic_pack_payload_invalid") from exc
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
    ):
        raise RuntimeError("financial_semantic_pack_identity_mismatch")

    material = dict(payload)
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
        or hashlib.sha256(canonical).hexdigest() != PACK_INTEGRITY_SHA256
        or supplied_integrity != PACK_INTEGRITY_SHA256
    ):
        raise RuntimeError("financial_semantic_pack_integrity_mismatch")
    return raw.decode("utf-8")
