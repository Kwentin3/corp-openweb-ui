"""
title: Broker Reports Financial Labels
author: Corp OpenWebUI
version: 2.0.1
required_open_webui_version: 0.9.6
"""

from __future__ import annotations

import base64
import hashlib
import json
import zlib
from typing import Any


DICTIONARY_ID = "broker-reports-financial-labels"
DICTIONARY_SEMANTIC_VERSION = "2.0.1"
DICTIONARY_FILE_SHA256 = (
    "30b395b13387cad5d3d51269bc3bae989bb3b524c9547053841dc5d146c569fe"
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
    b"c-qxk-EJGl6~6aV40zQ7q-(oy5!hFX#MlHBNf7BIMPd-E<w#m&$z^w!vedwUMZs|kCl(x}Xc53kiWa#mK+B}Hq9p"
    b"1Sc3+`S(sR!I>~Kknr0O>9g-CN}cINzi=R4=j_={_d<pO(~*RARf_XEdk<nFNChVOmO{i@HKo*xF)Ei2@|u5LOFt"
    b"6@8qTXn4s?pAA#9m0Ie->dH2%;j+<<B?NK7b?hw3VMkGEfI*f0@%F~I<_gnt?M_g%SD6G3R?j_Tzl~Ta;bd3xFiO"
    b"etqs=+wt1~;h4jviTfZsXc&~8tmKe91P2bzGTp0TTej87ubX&Kt-+r&K?YT9t6&AL5gZq~2{N6$x3VOBMv>Iy1ZA"
    b"Zzsu(r0o`jM1GuMDDW>{Wfw<+Qv9I|V!pL9LN_8IkoS8&=?uviDFpCWT{s$Eop#&6&@C*K&LwFuvP#9oq?6;I(|4"
    b"7pzve?fJaMoQCbyd7)|T)p;Xin;a&G9=uq$oCb{6c$32i48gp*6QD}W3Igt<-T`~$z(TO4)7a!bF6eWYOcLZk#K&"
    b"Y>>ApMcQ<7SkS3Q^3Ef*Ibtd}akt*$*-U%bCiE=m<)TAf=Br?G{z;=d&O@kKm{Pvi5r2Y=^rCpl#FsGl6bcR%hh_"
    b"!z)QKY0@Ok~aKn5TCH*OZfu+h+o6xv$zw#iK9Hthk1kKNpg_9U~!b})6ZuxJBs_TJd7N|`~iar?f3|meG<QoyRZO"
    b"kz~UpO=MUmDX=4^z{uU3fr;30(-M#9gZH}P$l$4pYkI)F#KTe**esZ5EtG$rd&^|estmyUJLoG_pt2Vr_nw97uC="
    b"UyLs}X=Z^Q`Fw4mvZ>KKKOebd1&pamdIKh!L^)$M{e25ApZr;(XVtH(efxHGeRDlgqQ*`>j3vS_30(TLCv-w7te="
    b"E3h_PUPWA~_tDxt*me+iwRXw#<f)+@E?5pd`*T)vg3xz1S}1nzA+7v4KLhTTO69fH^1||bxC6-sgoC$nCoeql28R"
    b"AXlcKn%%@mPC;5Vvq3_|zdv#TG1mtTWQZF*-WsEQYVKB$htXJENJ4+K!-^(LBMDPIRl_MLE#p&`hMAlozLM^FP;&"
    b"gQ%p%#Bb6)B{FAlbq3d=!8hx_dIpN1sOd8!$xF930ftf?fH;$Aa60t7J|P<|1dC{)Dr%LL*8I;j`~nMPQ92MUJ?)"
    b"{Xb`v*A{p5H6u%@)bJxZ1b#2sl9xjwCYBPk&Qt6}8QgLOeT3T6L{cr+7e*-qS0Hbyc2cPIDIHu=FW2fe5S9<Gh`X"
    b"B-YB012_58-+rG#h{}e@tE)8w>*!!Tk=Iw`n;w4Hf{n6GEo5tzcW*Z)WJK7XWIu-?H313x*t_w(&UxO@n!xuuszo"
    b"Eq5}YUV)VG3TiXfe1x&@5t^VFqV;Il_#=}SQL`nDjLQM{D&x}#i7~S%?nzR7Ly>a?2<;#np`9<_jW%h}nE`~0s}I"
    b"&zSKd7YMTUa1fdIe|U^t(`QnAL*jX_bO4Z+Y5JnqblLGamk@wcc2`sWn3ipD0drVr(z)3jV|J<=I|oIt?`l`0Ry$"
    b"*}x$78uBD-Crg9>=%Z)|M}#nUrr)HLpOq@*J=VeuL(m;$0h1GR2oLKks2^)IJ%66r-QPzQYo$%%au!E`FGf<Pq_h"
    b"L2}bFoJ<rFZ@p7z^<bv6;yj5X5NS+es3jhyu>KQnj(n6O|hnPD1&m&qWNb+`I&lCnQ5i`+Q@_YpL-QlVwc>&NzrY"
    b"$JI$(Chy!sQ!IsNtH2WREDy%OJ?JR)g4G(y_L^Vb1|l6_x-em^~-u)F}yH`HNIWW%YvKoX>KCm0=<p>?CP_mP1IE"
    b"l+KG3?b9ItEo||cdY%ClBU!9S_>bZ1VMrlc&s;i}iskAulm(@gd;cZ;8?HIVPUJ$CJP4O(MhBE}5Ej3*<jZ%D{Ss"
    b"l4`QD=;K%ZwTWNu?6>_C$(bri|p^(?HGg(O{x{s><X_4$tFwq{2>6(%X*>rmW7FAvQY6#03bN8pj`@K%P}d&qhNO"
    b"3M3G^a|D%B`y|~7|ZV#>cp}F@8#4!%TRg%beOR0)T;MNA*Sp6*=T-YadG`Yaj7b65P&*-6;~?b@h;O0rtv<bw)tE"
    b"`f&g(D(!?3YnaqBq6_RF~a#mmUQ97?_Ck`dGF;&bZ>@DRL3lSS)jVn@a2Gb(?5TGE_A;#5EA1T^1*-AkTVRK~NK$"
    b"k9aw|hipV@f(*ALPx-B*WxRW7G5NbS4E4)rrPvNM&p4Ije^SX)#UNU=^@KjYwg7(>AU4QTv{!=UctxOT~SWkYxr8"
    b"SJoF+$_tB?5(4=C!uq`lZ2cX<50SZ#86uC=^ctgInbq`hXzdQ2qCKB>G@%JMJ(dtk!5ckL9pCJYKgUx@Gqxwz6;i"
    b"><_&#C%E=#^93ECrzqaAx9C{N+Dr+|D;eTe3|G!+pUg6LAGLt5%I`AWp}5e@898zcIwQ{x0D`C2L>EUK~}4ebN84"
    b"<SW-mAtqlG&9aHgi<aUwH2LDMPrYxjJm&L#4~E8;+gOyj)+p~LOSj0laP_aqp89CN*#3_3HmV9*F|dwEel|hwE~P"
    b"E<aN1-BZwXHvaDnw-)nP7J>>JdxZWx1(>Lvh#uBtY21*c}A>R!R%Yl!NVfPaTbpK(gT!z4z%o-z(Ix<<iH`H-qR2"
    b"O$4D>t?{`+##y$SGmKU}ZSMaGdW#f>fBFMk;?xD+y76V7-ly)+i@p8Ijqjsfbr*>dKXEuE-|xNDU=>L*2q#*}z1E"
    b"hD&R;-h>P)oUAZL02xmyRPXfYOah6c7oXhKr=(=D;p`?^0P08;FFiW%IG3%JN>FE`oObmSfovr?jA^>H7~urnWkC"
    b"q3;-feITv*-OOtevkZ)c2lvgtl0%bq|!=yPHSrcYZ82cXI(1IS+Wl+p{9a^s2}@my$_<(NLEB=8kpmMBGMj^R7(="
    b"8YS4Z9%t_ctd8KWQ_$Z_8c<eafqh>Rk;NZ@<o@`5gJ5hdDE8Fwydx^(_(yH!U2r6)p2!(73T``YGt)D`L3j`Q)p*"
    b"|e#fORWSsdcWP_segfu#h2W8XV$_hF4I)Uvq`M+@%2bl-PM5vhH6~#RrU=Fas97!}H0U-zBeGS>&xPQT)*4CEK@y"
    b">j{JgQS-gtwOR5M7?5MtK?O`y$RM=3wGeitb3e=S<F{#7;LRYNk|2FG;qDbb!gQ?jvL&-wIYTUmQ>bbOd`$4mFJw"
    b"N_Soe^?7>BJZo~AD?oHK&lfo})YS{0R6j0N?%yviFHPzPW!BA<$|qO2#gk3tfzI$otYmKZYCN<Ych-x(kHK*GzX-"
    b"7N9+D!x1{<-I$yb^CP7{`*SWdI)Y+1y(?=zbXtcPsNwOhdEye57(tvz%;-au})(u))$z`Pl*Q4qhwhP_l_#FA;W3"
    b"J9`9CZC4PA2Eig8)%!2M<+wm<DHzAaPvWP2HqaoQRNFm#{YZDCMeK<UfJeujo>4>8Zcpp{|l_Fo1+nW#ren|UDbn"
    b"Pu{m^RO?;m6b%x+49V$*B=PV!$wnn=tBdWvYu`#4jF)w{zIVLM9A*c|6&xh9@U;7tk$%g&"
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
        or len(payload["labels"]) != 12
    ):
        raise RuntimeError("financial_label_dictionary_identity_mismatch")
    return raw.decode("utf-8")
