"""
title: Broker Reports Financial Labels
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


DICTIONARY_ID = "broker-reports-financial-labels"
DICTIONARY_SEMANTIC_VERSION = "1.0.0"
DICTIONARY_FILE_SHA256 = (
    "182e8d7f3604ad3d06d93c4d913df17979f21aeea669123d70c10be9d9652850"
)
FACTORY_REQUIRED = (
    "Tools.load_financial_label_dictionary is the only managed OpenWebUI "
    "delivery entrypoint for the exact published Gate 3 dictionary"
)
FORBIDDEN = (
    "The Tool must not read a runtime filesystem path, use network, Knowledge "
    "or RAG, return a partial dictionary, or reinterpret financial meaning"
)

_DICTIONARY_PAYLOAD_B85 = (
    b"c-p;LUvJ~a5r4l=vG7w0NIoYAv_;+&Svd=EY{RlIDVl<yskKdnA_bE2*$56e`<l4L6**jxqD6rGDN^LEfP812XrC"
    b"p21@bHOlk_*cOKM3=7fJ5r!IHSUoSmKd&CGAspWk6@A+Yv&%QOzSAK0F|@IG7E@x9NuZ}`0J`C(w}nIXSt?AosBT"
    b"DIvJj=94fqiI_q)|>v3aq#X!i6m)5c5@`CtOS)a5oIAFkZ%Rp-3@I^*Wlg7rNt#R9hzY$puvsp4_51qmD;kLXm@r"
    b"TJJ{z<!whNqy`}elTVDEodFgj@-fXvh@4$30_c@-m5vASUy~TU2GCyoPwq=LqJr9bdOUealbUJR?seYA>jm`B3N|"
    b"Q`7RM|N)e9z%RJmeVx4?`U5#=5a8W5JFY*y6DFq1;Ez^4!ojt&r{7hdf~6K4-4&az?Wc%Fxqp!Z}T*><Jl<#M#yJ"
    b"`|OWGtUP}@u8!ZRRkt_mTYoS%wl}LQl}1hJfMqRiVw*i$75_6ij<4fk{5l@QJ^T&gZt{$Yq08h6zAxi0!^aRam&x"
    b"O}mz?0&Fuq{Pm+A$2h|jS2D(=QF<A}xQ@oNZ4j+4{mIo5X<M|;CW&XMtOpSzj*Vw@Dg(qVE6iBWtB6_UrvGsqk&Z"
    b"6Lg#JdI!A8%nS^Dr%lQNxsTyo;;bX<l=(b`%jr_P0w(>(3q&<e@H(Dhq=Kn_e-qp1vUjliGBD<iN$@g9MlsAi=Y+"
    b"^@nih=_=ouWF`My2v(<KZP}t)K-R_yyF!Mp@NPpbu_}0D|@SB2xsohRs?l|0dXoveZ<oC#lP;(fcXVyucCSPdQ(K"
    b"l*@p7j}P+Ck{sI~_W1wx#%fRGI>U%k{>_dZV&B8w8;!l!QXB;%-Sg_9dqNA{Iq)FSBwa{EKHgRUc>Q;qyEj1Zd81"
    b"!V~e%8vrp6M#lg%FdbfEK5z0?o9vaU*+Qc8?eK_^%Hq5L>}l!%sD|8Oao!AW4Nc~CLKtj_!7Cx3%oi!k3`XX=7Uq"
    b"gzk|>T!8Cp|?Ezd_{M*?D|B@c2&mZk7kr^cT&<x7gvo7R`ZBl{=MW{3pc{W>B=j1++IbNoC9TJAXd^JeCZUoBn^>"
    b"?U`c)5pqk{Xu=Xwzh24*Q)CuO-R;X!<5(XO;^LsMHU8qF-~dmwLW{Uoc?Mw5aB$LnmB(O$+>OX%?w5e1)HjvWd{4"
    b"1W#$HXDgdCg{Eq3ASdcS$x~<O<ZZ7k7v2WWBO=o)OeTP#(1f6!Q#d2u;p1=(Q5Z+(p?LP6PDp_K=h><BF`CY-y5h"
    b"csQW~56_%dbUjz5tfHR6EIE*Ld?poU}VVOsnhL8|!QTe~`+W2a+N1gxrN(gY_cLMS6NWC_QR%H_QW7(}jr3oG68t"
    b"zKy>D1ri>4jjf}xC9Lh+pv-O4$qa;(Cx6Am1+!gnOCE&N1NR?AXi#oEzndJhcQgzC_wmoa`K5%a*&qj8uhT{$*pP"
    b";s9l2za9Jh>eilhs))E`Zg`lp6(eQm3@S!-;)5y1b(#+Ra80l={3CAnoV9=C5swK#|@8bq7Zyf93@5amQdJ)fVih"
    b"&EHjITv6is9w#5eW|lhp$jo1Kwu%&t*hjzbj7*YhRWP4vU&0qB7;(OImI7<Xn8F@f5zrJc9@~L1YSWPDybMLv5qU"
    b"sh05odO*K0WDQ6MexS)bNsSMA^EmFTIJ7^og37;;=bdH5&#f#+R(*+%g_0%?1ku+wFgm19*ndqg4f*%#JQizH%2|"
    b"o`lO82wU@_Madtb%dW*Y5vH;h=f6PfgObB3FdEQ>|Gm_!SgVihMp*DAWa7neRQ!6@WpJrgMwvxQ)JBsV#Yg<C#R+"
    b"DRom0l5r8y3m$qd&d`;2=8pxzfkvUwGW|W<WoYI6Jv0qzLBfz@^G=~A^eEj8McqCY%v+{+$+L-}QmDV(AQ0&`9|?"
    b"_-9aq6-fEp$}Ff-MjD=4$3WTrY$sa7|)Ys-eBGXOunYHM5LBS4iUq7RqyF62rTN1-bdtSY<gC=|HNiMgsaC&N*iN"
    b"Qok060ep;SzJDVg%WaK;6Zd}c#v(OYT>{)EKVsn$Y{^4+fI?e#xTB&LzHw@Q%Li+yX*OAjp<_1$*xo;M%hHheoJO"
    b"iQMSzTI&u!|))aYU_NH-KK9%Y<7+tdUk}uQD7)f2HhxOKGWvx-EZq*6XE0xXr6H@xO0>VfmfC{Qfi6C=E`6Km;4w"
    b"=wAEa{n4hnKp!0LaE(5#}5+)Cz>|hu)j+5~m4@e@T6kzX?5VTnoy}$`KJ4TgYB%Ag}8BOq5UzzmojuM5w0)FJABA"
    b"ASzDhj1xl2zUNSiEKwME9j*81p!zhAP?h`x5utg~#6+q%lXa{|ML-o!90_GHyED7YJ9hd2${|8{QhHX@-4oe1A}7"
    b"Bie`C6@Sb<oUZzl@qV)1ijPQrBe7nb7daWOcnUaMsXbUA<bL(Xp%nm>(7x?}>xgURy)(FqUpmpP)jKc<Vi?1hX&p"
    b"9-9JC4UFtW{A?tC&tJ1t(BG9>hh$5qm)5p{&@`jf<Eanx;pvlYaDB;TlbGgkQ~zt5V92cXZ%3xl!g3(xKfZrP<Ae"
    b"ADVP-{j@w;h>d6NmAWn|eap=Dx@)=Z#e4Gyqfz7@i7V=^>>+_k<cROP*pC-h`jCjc$S8$QONVoZxc{nSAf0SH9{t"
    b"qP6q7YX<sd@~6-c|Rq+1-!+P9C#&=+~n={{!Y#1{w"
)


class Tools:
    """Expose the exact published Gate 3 financial-label dictionary."""

    def __init__(self) -> None:
        self._dictionary_json = _verified_dictionary_json()

    def load_financial_label_dictionary(self) -> str:
        """Return the complete pinned financial-label dictionary JSON.

        :return: Exact UTF-8 repository dictionary content.
        """

        return self._dictionary_json


def _verified_dictionary_json() -> str:
    try:
        raw = zlib.decompress(base64.b85decode(_DICTIONARY_PAYLOAD_B85))
    except Exception as exc:
        raise RuntimeError("financial_label_dictionary_payload_invalid") from exc
    if hashlib.sha256(raw).hexdigest() != DICTIONARY_FILE_SHA256:
        raise RuntimeError("financial_label_dictionary_file_hash_mismatch")
    try:
        payload: Any = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("financial_label_dictionary_json_invalid") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("dictionary_id") != DICTIONARY_ID
        or payload.get("semantic_version") != DICTIONARY_SEMANTIC_VERSION
        or payload.get("status") != "PUBLISHED"
        or not isinstance(payload.get("labels"), list)
        or len(payload["labels"]) != 9
    ):
        raise RuntimeError("financial_label_dictionary_identity_mismatch")
    return raw.decode("utf-8")
