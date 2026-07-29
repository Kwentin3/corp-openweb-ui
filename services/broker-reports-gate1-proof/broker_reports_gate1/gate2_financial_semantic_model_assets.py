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


CONTEXT_V2_MODEL_ASSET_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_context_v2_assets_v1"
)
MANAGED_ASSET_FAMILY_ID = "broker_reports_gate2_financial_domain_assets"
MANAGED_ASSET_FAMILY_VERSION = "1.1.0"
MANAGED_ASSET_FAMILY_MANIFEST_SHA256 = (
    "4e5328554056741ecb783d130a5fd43034a6876484a25c98dfdd5e68bf76499d"
)
DECISION_REASON_CATALOG_ID = (
    "broker_reports_gate2_financial_decision_reason_catalog"
)
DECISION_REASON_CATALOG_VERSION = "1.0.0"
DECISION_REASON_CATALOG_INTEGRITY_SHA256 = (
    "d7290593410cafd6b35281ed3a6159802f0d7e87b7a085f3ec2cd2b46f4a3e15"
)
DECISION_REASON_CATALOG_CANONICAL_SEMANTIC_BYTES = 3603
DECISION_CODE_CONTRACT_VERSION = (
    "broker_reports_gate2_financial_evidence_decision_v1"
)
CONTEXT_V2_CANDIDATE_PAYLOAD_SHA256 = (
    "99be5272ebab4e69e2533391f381bd27682496148f760e1e4a171f9e7162cdad"
)
CONTEXT_V2_CANDIDATE_REQUIRED = (
    "load_gate2_financial_semantic_model_assets remains the only "
    "closed-world managed financial model-asset projection entrypoint"
)
CONTEXT_V2_CANDIDATE_FORBIDDEN = (
    "The non-active candidate asset projection must not read runtime files, "
    "use network or RAG, duplicate Pack meaning, activate family v2, expose "
    "repository paths, or reinterpret reason semantics"
)

_CONTEXT_V2_CANDIDATE_PAYLOAD_B85 = (
    b"c-pmC%Z}qV7X1}MYqufEmS4Tf1IcV=FhFKjK_F1%l})rnDkSA<O{4yO4k_7Ixm=w}Po_3yOT4dh&pjmlC6OeQQ%0"
    b"ATxWhleJ#Wl0IebZY*ENb<=}jq>>x@$#3zI|AYteA$RINyswbEP*#hX&;uJ_3z;k`c@tNc(p&wcM;;kiAMFSW5P_"
    b"v%de<jV#huzZSGDv5=aHJ`{Lna)`6$|Lub&qBPFExZ^>r7+rCE_`_=>&9IFz#*NLBrWLX`JBPqu~z{BVVZ_SsJis"
    b"ZHw1tGp4HB-e%QsFjfpw<AgMgB8bUN`BvAM@IrS~SxLPDFajkSnzIRkUok-)OG!dKGlM#4eMxS}xMa!{H=gTMMPo"
    b"*YxJXNN*a8_R8|F%d}+xGVv1eoB!(WNffY02#n4Lr5wCmK-Zv@Skrcts7Kz0BTN30$LRybA<r_)x~D$ulgqr{hS1"
    b"6VHoHShLOdX|Z3evsCa}ZmLz0?=q4rzR8OHF3syyZfUozwmjVx^@>C;WL~W|^_s6JD-g6%HHkrlPJo{x!eY^+ii="
    b"N(FqTzz7Hu`XE6==95*?T23=7_>X1Fp0h+AI!xfj$TxRnuH)8kdIy=tip9{gx?C3Z9p^)^QENRZew0L7083#NefQ"
    b"^<D_+_YTj(Jqka($2%LU&fvs5^Z38RL<L>^h5VfJ_H9S%quOXDdugZj(vdXg*!0#_g-0YjC<C=+B5%T7`od#1pwK"
    b"_3*%?5nt&+_cJ3p)&+O*vKV;`F?ktzrLd&VfH*!m!!P1vhJ7lkC=8*hokc?+|!orhSfw8PLc9wsPjT{5wx8xS1h0"
    b"$YjOgYwT^?Ogvz+B&jwvn6`K?uounEQdD2l%2LEU^;I>){+RE2SkG;aKR6x;b8imt%4#L<!o-p15P4#7QfV30`JW"
    b"gExTpPHcmVUSG2cIL?Rkko?2kVa=ew;zVvHKZoQOa7ECEK<XEwHWk4E8b->I_6t@astz@nIwpQ|f3u5$B;i5aG2A"
    b"6+Fi@7A)yRS=fhGGF{7kXh9(<cxGT&yFkA(1$e8=3N;ngd_ta)Ow1joLQL&j<fX`nyNg8lHfpV&HI=EZ_>Em@xCn"
    b"-A&gL%ROR2wE`Q;}jHNHVR-(U6Ta_vpS~&7R&+Wrn#qe1kUyiFoldPAImOutmU6o+qY<`Xuv^iiiZ^K0ebgOpJ!V"
    b"Iwj!`QlI_Z(r;|bO3%)M4m7PGHim*bMwnIuXGVv=_2Ykl2(=!eGTOq6(nDXvc{Y+Ne;)0oE4qeotF_%3yGG3r?4<"
    b"N@Dx+VL?+g|wIM#3LSlZ`A4p%JdT5D3HP6)>jHh_-~{UiI)Tt@uV+{8kbB$o^_UeJzWxr2l~)=I_x%{Yn>Vv~*H6"
    b"^hS6z<Nqpwyg_Ml_z<Y!M~S<tVheu2K}CXxjFIe|4N)ZnmsRsf^8Vg8UUjeg^GfKyQ3B(5Jls#-C587{Fq|JCRY5"
    b"*3b9<SWfIA>{_+|s%E;NxjBzzm!IGUrZgpuPlfcvWib<&T{nvjrVKY#yEwojK?x(Ip*phhVby@f7{VcHs4JT3-w4"
    b"E)#tkFW}A#=Ws0BXSQ!=MgaQjhT&3-YE3XNGfhEaRtfbp}6K>6W14$`^LOZb&N8FaT<wodZot=PML8loI``A-ukY"
    b"IWS9rTs2N{VBuD@lv$Kq2e>s)LQ}B2$J=DB$1Wd5mw*38<pf_$+<5lPea7*4Q0e9CPl@}<=D-<)g0hBW8eRMPK2D"
    b"7ZPWx7nm+4<3FIdt)VI5)#3t_qO;>+NGr#VX$w#X2oE+jT~w+U`~|Tcy0H<$9H_)_k+uZq~as48(pXYbgub?5Y|M"
    b"_xr$_uR;E(ylgD*`mRIg%Te%rEbzf4iC1Y=aQv->+-0j3ukwxDN<lj+(rmj;MJ}^-or|oJd7c)c;&N5<Tx=+%ZM_"
    b"R)J%)J=+6CtuY%fy#gD$-+V<dA~aqvUw={_c?3zx0fcr{%(xjSK1!^0)pY2LXLwx-Ce&W8Hu>5L2uZ^OPuIB-GuK"
    b"u2sJL2s@;ZMa*Pjd8BTT$rcmyftTPf$ix0@tT(jgnb#<Kh7@9JC%*%m1<&#9=z@N5F>_xlQ<uh@xDA;U~%N|rK#g"
    b"yJkt9P13tv5d7OhKL15a~799H~UT{a}k5@T@Mu!@dJ|kUYAJ_a_$oj~|P<8`uzWVm_%_#A+o3J|C$o~rs!f|8zjp"
    b"zF7&zRnLSh><W#T~oYb1w5@U+pQ&c#*EQRkdAJ>3*}$Mb3BI8n=Ef_-a$_Xf3O)C@_h;BIjZ^clzgl<hhw<$@BAn"
    b"0qkb^fB"
)


def _context_v2_candidate_assets(
    *,
    active_pack: dict[str, Any],
) -> dict[str, Any]:
    """Return the verified non-active V2 family, Pack baseline, and reasons."""

    active_pack = copy.deepcopy(active_pack)
    candidate = _verified_candidate_payload()
    expected_pack_identity = candidate["semantic_pack_identity"]
    if (
        not isinstance(active_pack, dict)
        or active_pack.get("pack_id") != PACK_ID
        or active_pack.get("semantic_version") != PACK_SEMANTIC_VERSION
        or active_pack.get("integrity_sha256") != PACK_INTEGRITY_SHA256
        or expected_pack_identity
        != {
            "pack_id": PACK_ID,
            "semantic_version": PACK_SEMANTIC_VERSION,
            "integrity_sha256": PACK_INTEGRITY_SHA256,
        }
        or not isinstance(active_pack.get("full_compact_snapshot"), list)
        or not active_pack["full_compact_snapshot"]
    ):
        raise RuntimeError("financial_semantic_context_v2_pack_identity_mismatch")
    baseline = candidate["semantic_pack_source_baseline"]
    type_ids = [
        item.get("input_type_id")
        for item in active_pack["full_compact_snapshot"]
        if isinstance(item, dict)
    ]
    if (
        len(type_ids) != len(active_pack["full_compact_snapshot"])
        or len(type_ids) != len(set(type_ids))
        or type_ids != baseline.get("accepted_type_ids")
    ):
        raise RuntimeError("financial_semantic_context_v2_pack_baseline_mismatch")
    semantic_pack = {
        "schema_version": active_pack["schema_version"],
        "pack_id": active_pack["pack_id"],
        "semantic_version": active_pack["semantic_version"],
        "managed_asset_ref": active_pack["managed_asset_ref"],
        "consumer_contract_version": active_pack[
            "consumer_contract_version"
        ],
        "integrity_sha256": active_pack["integrity_sha256"],
        "source_baseline": copy.deepcopy(baseline),
        "full_compact_snapshot": copy.deepcopy(
            active_pack["full_compact_snapshot"]
        ),
    }
    return {
        "schema_version": CONTEXT_V2_MODEL_ASSET_SCHEMA_VERSION,
        "managed_asset_family": copy.deepcopy(
            candidate["managed_asset_family"]
        ),
        "semantic_pack": semantic_pack,
        "decision_reason_catalog": copy.deepcopy(
            candidate["decision_reason_catalog"]
        ),
    }


def _verified_candidate_payload() -> dict[str, Any]:
    raw = _decompress(
        _CONTEXT_V2_CANDIDATE_PAYLOAD_B85,
        "financial_semantic_context_v2_candidate_assets",
    )
    if hashlib.sha256(raw).hexdigest() != (
        CONTEXT_V2_CANDIDATE_PAYLOAD_SHA256
    ):
        raise RuntimeError(
            "financial_semantic_context_v2_candidate_assets_hash_mismatch"
        )
    try:
        payload: Any = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "financial_semantic_context_v2_candidate_assets_json_invalid"
        ) from exc
    if (
        not isinstance(payload, dict)
        or set(payload)
        != {
            "managed_asset_family",
            "semantic_pack_identity",
            "semantic_pack_source_baseline",
            "decision_reason_catalog",
        }
    ):
        raise RuntimeError(
            "financial_semantic_context_v2_candidate_assets_shape_invalid"
        )
    family = payload["managed_asset_family"]
    if (
        not isinstance(family, dict)
        or family
        != {
            "family_id": MANAGED_ASSET_FAMILY_ID,
            "semantic_version": MANAGED_ASSET_FAMILY_VERSION,
            "manifest_sha256": MANAGED_ASSET_FAMILY_MANIFEST_SHA256,
            "runtime_activation": False,
        }
    ):
        raise RuntimeError(
            "financial_semantic_context_v2_family_identity_mismatch"
        )
    baseline = payload["semantic_pack_source_baseline"]
    if (
        not isinstance(baseline, dict)
        or set(baseline)
        != {
            "registry_version",
            "registry_sha256",
            "accepted_type_ids",
            "deferred_candidate_ids",
            "legacy_python_status",
        }
        or not isinstance(baseline.get("accepted_type_ids"), list)
        or not baseline["accepted_type_ids"]
    ):
        raise RuntimeError(
            "financial_semantic_context_v2_pack_baseline_invalid"
        )
    _validate_reason_catalog(payload["decision_reason_catalog"])
    return payload


def _validate_reason_catalog(catalog: Any) -> None:
    if (
        not isinstance(catalog, dict)
        or catalog.get("catalog_id") != DECISION_REASON_CATALOG_ID
        or catalog.get("semantic_version")
        != DECISION_REASON_CATALOG_VERSION
        or catalog.get("managed_asset_family_id")
        != MANAGED_ASSET_FAMILY_ID
        or catalog.get("code_contract_version")
        != DECISION_CODE_CONTRACT_VERSION
        or catalog.get("runtime_activation") is not False
        or not isinstance(catalog.get("reasons"), list)
        or not catalog["reasons"]
    ):
        raise RuntimeError(
            "financial_semantic_context_v2_reason_catalog_identity_mismatch"
        )
    material = copy.deepcopy(catalog)
    supplied_integrity = material.pop("integrity_sha256", None)
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    reason_codes = [
        item.get("code")
        for item in catalog["reasons"]
        if isinstance(item, dict)
    ]
    if (
        len(canonical)
        != DECISION_REASON_CATALOG_CANONICAL_SEMANTIC_BYTES
        or hashlib.sha256(canonical).hexdigest()
        != DECISION_REASON_CATALOG_INTEGRITY_SHA256
        or supplied_integrity
        != DECISION_REASON_CATALOG_INTEGRITY_SHA256
        or len(reason_codes) != len(catalog["reasons"])
        or len(reason_codes) != len(set(reason_codes))
        or set(reason_codes)
        != {"ambiguous_registry_type", "no_registry_type"}
    ):
        raise RuntimeError(
            "financial_semantic_context_v2_reason_catalog_integrity_mismatch"
        )


MINIMAL_MANAGED_MODEL_ASSET_SCHEMA_VERSION = (
    "broker_reports_gate2_minimal_managed_model_assets_v1"
)
MINIMAL_MANAGED_ASSET_FAMILY_VERSION = "1.2.0"
MINIMAL_MANAGED_ASSET_FAMILY_MANIFEST_SHA256 = (
    "8d48e23a876844376443eeb357bb381fe0443c2bf1525657b6f81979408c630c"
)
MINIMAL_MANAGED_PROJECTION_PROFILE_ID = (
    "broker_reports_gate2_minimal_managed_projection_v1_candidate"
)
MINIMAL_MANAGED_PROJECTION_PROFILE_VERSION = "1.0.0"
MINIMAL_MANAGED_DECISION_REASON_CATALOG_VERSION = "2.0.0"
MINIMAL_MANAGED_DECISION_REASON_CATALOG_INTEGRITY_SHA256 = (
    "2510b57b51749a14f76b987cddaa3eea19f1bb975a97c6c089565253dc3593e9"
)
MINIMAL_MANAGED_DECISION_REASON_CATALOG_CANONICAL_SEMANTIC_BYTES = (
    6393
)
MINIMAL_MANAGED_CANDIDATE_PAYLOAD_SHA256 = (
    "6211a7668deb14191cb2a215d726d4e7782e43e4834477cb0fe49e86510c62ca"
)
MINIMAL_MANAGED_CANDIDATE_REQUIRED = (
    "load_gate2_financial_semantic_model_assets and "
    "Gate2FinancialSemanticV5ProjectionFactory remain the only managed "
    "asset-loader and shared Pack/reason projection owners"
)
MINIMAL_MANAGED_CANDIDATE_FORBIDDEN = (
    "The inactive minimal profile must not alter active assets, read runtime "
    "files, use network or RAG, embed replacement wording, build a Packet or "
    "Choice, or activate provider transport"
)

_MINIMAL_MANAGED_CANDIDATE_PAYLOAD_B85 = (
    b"c-qZb%aYqR7X1|z*J>3>iF&kGlbJZ#WRfapW|K;>Kme2wlY~Nm>Tq2B?{h9lO4Q44w`I?G(e4I$-{;-~fFA;>gtp"
    b"pLX|1@$e}X$+m`(8bA>g}Rp_NUYNu{<sW3|JJ!DG-=qTtr*Tq~L8y5g14yhwGmYg{l1c;mLF)~-#h<F2ug$Q#$xD"
    b"&5Cv1Phhak~@`F#-)YcE6DU_Q!Vj!R-5;#hDSS7JDYCsZalJc%jHRs^HLXWy5r(K-{@*{bbw5C%W%1=oG#Lh;l&a"
    b"{n?_T#!W4xP6k+PLD-?wOHHwoR?6bi>>+D<TP*OXd6$)OeLc-v0!L}*+plTA7idS$5zcp5+Pg_;tS803-Mk`&C_b"
    b"OF?@p9)Sg{fT4txKP@+oqM$n{8&AnxY%*|2_$HSvKb$2qQ^>RYP2mt0b>mFW^*}zE>^6?BDY%1<zE0wNvj+Em04z"
    b"8P5m|1#eTo8azX?a%$5Re9Plxfp_903bSOHCDC%e=FvP~F0%D%DWv3lrWB9Xd6Z@AWy04>u@K>Eoh*_#nMpBA)-$"
    b"z+(L(1+w1O%DEDE2N8b!)bMp)>=N_Vx|Ytz_t&kK(#nT~SN;bE_8suyLv=D8bdK`esT(kIt6ctqGJRZ1FMCv(7%7"
    b"p8a%Be(~MuNe~MQ3a$ZH<)}8j!nsR)yWZv5DK8BtTi=-Y{gcU{NVg++aldZ9t3dHX^~#3m0ZT_5Lur`q2Re(WV0k"
    b"*MM}>2B1+b)FwR4{RI6pS<l!pGXG+9E#@T$4&r!=L8LK~f8%@J$NZA@t`uN+24r<hmaB`!qtJ~DIyBETo6rf&CSE"
    b"3(87LQTp6J2Pj)bgBG1rUlR{j<@vvJ5RHT+uR9DF*yDRs$l8@3}4rER2L%);Lxf)>Qh>M&V`B#Dt+<bc%H<->`H4"
    b"k4FBZYI9S&od!cX(moR}hyXb}kDHg7-ZX^z8*XsN3fOVXJ&oNNw4D2O&xmgL7Cd9<oKB9%=yC);2LCW{#xblgTJa"
    b"H>nw6#=`R{GRM{1y>bCXVj3hZOhc2vk_M{T2I{}MP%)ehpWMSbay%0d!vVvsaY4x5<<Q&k(w2$TA#ctQ_5=eDpyw"
    b"8x&fWlo80r7;_zWyBnKg7lv8B&lesgIAQt@yvY;{%Ov!S#pPwU`K577`#J|2=zcS>V%{EAUKkSv0_!_COx(hgUP+"
    b")NA*WJZ%8UEc(S*HQ4-KK+v^Smy#rJBEA;fX$_9ArOETUeOt10UWAHa-+X`ASHCSz)m=D3S@BENsxgs}EpJKxP{^"
    b"MIVkEd}mVc0sbIE)t$;p`!tzhMgVrajLS4fIhf05y58YNTKkXCJ_XS){or&SC8nS2qQ63Rak2XHm@P1N71Xn(0B)"
    b"sN%k>1>_tFmHaPVHYIQ%3P@xB^BAJ0Ncs6Hrsn|QZX%$T-h3*yMvK?!d>-vVu*X54dDtKD{IoSl!%%7K0milfai;"
    b"JF%|awc`kwem{;5*k(|)aj{4u30YngWTSclPovy-8Ek`2THU0N!%sqZ}>HcHxo$xhijS2qG%Oy7DNRjJzd1DS@o-"
    b"2i2b0qpz=Pywt>{b2o!Is8hJdhKX^!|p(D-XPWDQ>1n|$S+9xTkz05LmrQK4{;18!rUh#{|pL?UqWHk#VF6=$K<v"
    b"AHV*qN7NR^#)sdn4{_Tkd^G+Bduo8zm-*<=opcetUD@!l39R5-V9VzXSqJFM=Qi7(Q7!j&R*P&&ORQ3JH?VHrog>"
    b"1($6K&C4I-5w+DBGp^jN(u8GEB@NK{-Xa<z0&J#b1Kk?L)>3M4~*I(V*~gaMo?tDMNHR@xT;K4LTBS7aHnM`wXf)"
    b"j-uF=`&m%Zh=Z_aE*uIxQ;{7iF{Q&J`dXta%qCS|L&nJf`1+(4T_vFC|A*9wjjU&*j;V}K+-a*$SgQzQm^Y@_qa!"
    b"?8uoJ;C4QZg{O-6gg15Xj~_SkdS>+MRD=D|EwQ247Ssh>SbvAi}Vh>|pQ#UTzvlBoSgbaiV&eRGPsHv_zihW=N_z"
    b"^@<ti;jnvtTg*#RvKsNtDU8IfoNs>Kpo?{v(n*sRbuWzL8b&JkKyciGv|+6R1YGlOJe$|DV*M2;`M@2UwM}DgZ3("
    b"MzvxVL?gityqrron=`f)VV?<M&mBn8*<=Yxhu^tvDJL~glaVKW$C*`g-<d9`QeD@1mhtnvW(7_6cnp`p(9Q4<Sl$"
    b"~y*(k)x9F}S%i^&6kLD`$pli5U~x^+3Nmje)JaTIIJhm*f+Fb3!{AD>sHopV98TgU0S4d%2A&xOm@fC`Ls(A+ky-"
    b"Nu6n!D!RwYLzPO6E}r@Ugud7TrWCu$(Uhk*@0yTRqH%l<hdWk(r`z4KKIXizYI46j&-eru66Pv;&)<uGJ}_QZ;NP"
    b"#_gT})>=(T%d0>u~H7(=Db70CW@m%Eblm5OJ4wOp*`^VxENA4+AjWSM2NRg|j`3nI?)D1iW07x^k$FW2*MB^I+#e"
    b"4;$pu6g4wJQV(qKHWVAD7ae%>b5D!yi_|?5zyK%`Sx?rM|b=;Ub&B@j~M8|d#8vxZB%4z1&Y)*b<RE1`owjl>DpT"
    b"s{8WMdQ*r+>VCd1??j3}C%#Mn?AAP|KPRdT(**b++b-Oc~CSLFZX?r`w`mTr1zms1MQg0E9soSYQ_)dMqaB#mNGo"
    b"YA02!5(u$3mTmee9dZ=#vqIyAN06lpPM)DF*7sZ$moQp3i+d*7(D<k8C^(vxMW{T*y^4oAE4O$fXo&rIIjOE<+K^"
    b"Xr9L+%48geiO9H|<vbP(6{=;vqVjcSF5?~w@QV1KpZ^QY#zh?"
)


def _minimal_managed_projection_assets(
    *,
    full_pack: dict[str, Any],
) -> dict[str, Any]:
    """Return exact non-active family-v3 Pack and reason authorities."""

    full_pack = copy.deepcopy(full_pack)
    candidate = _verified_minimal_managed_candidate_payload()
    if (
        not isinstance(full_pack, dict)
        or candidate["semantic_pack_identity"]
        != {
            "pack_id": full_pack.get("pack_id"),
            "semantic_version": full_pack.get("semantic_version"),
            "integrity_sha256": full_pack.get("integrity_sha256"),
        }
        or full_pack.get("pack_id") != PACK_ID
        or full_pack.get("semantic_version") != PACK_SEMANTIC_VERSION
        or full_pack.get("integrity_sha256") != PACK_INTEGRITY_SHA256
        or full_pack.get("runtime_activation") is not False
        or not isinstance(full_pack.get("full_compact_snapshot"), list)
        or len(full_pack["full_compact_snapshot"]) != 2
    ):
        raise RuntimeError(
            "financial_semantic_minimal_managed_pack_identity_mismatch"
        )
    return {
        "schema_version": MINIMAL_MANAGED_MODEL_ASSET_SCHEMA_VERSION,
        "managed_asset_family": copy.deepcopy(
            candidate["managed_asset_family"]
        ),
        "projection_profile": copy.deepcopy(
            candidate["projection_profile"]
        ),
        "semantic_pack": full_pack,
        "decision_reason_catalog": copy.deepcopy(
            candidate["decision_reason_catalog"]
        ),
    }


def _verified_minimal_managed_candidate_payload() -> dict[str, Any]:
    raw = _decompress(
        _MINIMAL_MANAGED_CANDIDATE_PAYLOAD_B85,
        "financial_semantic_minimal_managed_candidate_assets",
    )
    if hashlib.sha256(raw).hexdigest() != (
        MINIMAL_MANAGED_CANDIDATE_PAYLOAD_SHA256
    ):
        raise RuntimeError(
            "financial_semantic_minimal_managed_candidate_assets_hash_mismatch"
        )
    try:
        payload: Any = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "financial_semantic_minimal_managed_candidate_assets_json_invalid"
        ) from exc
    if (
        not isinstance(payload, dict)
        or set(payload)
        != {
            "managed_asset_family",
            "projection_profile",
            "semantic_pack_identity",
            "decision_reason_catalog",
        }
    ):
        raise RuntimeError(
            "financial_semantic_minimal_managed_candidate_assets_shape_invalid"
        )
    if payload["managed_asset_family"] != {
        "family_id": MANAGED_ASSET_FAMILY_ID,
        "semantic_version": MINIMAL_MANAGED_ASSET_FAMILY_VERSION,
        "manifest_sha256": (
            MINIMAL_MANAGED_ASSET_FAMILY_MANIFEST_SHA256
        ),
        "runtime_activation": False,
    }:
        raise RuntimeError(
            "financial_semantic_minimal_managed_family_identity_mismatch"
        )
    profile = payload["projection_profile"]
    if (
        not isinstance(profile, dict)
        or set(profile)
        != {
            "profile_id",
            "semantic_version",
            "status",
            "runtime_activation",
            "response_profile_status",
            "transport_eligible",
            "semantic_pack_dependency_id",
            "decision_reason_catalog_dependency_id",
            "decision_reason_catalog_schema_dependency_id",
            "decision_reason_catalog_contract_dependency_id",
            "model_surface_contract_identity",
            "projection_owner_entrypoint",
        }
        or profile.get("profile_id")
        != MINIMAL_MANAGED_PROJECTION_PROFILE_ID
        or profile.get("semantic_version")
        != MINIMAL_MANAGED_PROJECTION_PROFILE_VERSION
        or profile.get("status") != "inactive_candidate"
        or profile.get("runtime_activation") is not False
        or profile.get("response_profile_status") != "not_implemented"
        or profile.get("transport_eligible") is not False
        or profile.get("semantic_pack_dependency_id")
        != "broker_reports_financial_semantic_pack"
        or profile.get("decision_reason_catalog_dependency_id")
        != "broker_reports_gate2_financial_decision_reason_catalog"
        or profile.get("decision_reason_catalog_schema_dependency_id")
        != "broker_reports_gate2_financial_decision_reason_catalog_schema"
        or profile.get("decision_reason_catalog_contract_dependency_id")
        != "broker_reports_gate2_financial_decision_reason_catalog_contract"
        or profile.get("model_surface_contract_identity")
        != "broker_reports_gate2_minimal_model_surface_v1"
        or profile.get("projection_owner_entrypoint")
        != (
            "Gate2FinancialSemanticV5ProjectionFactory."
            "create_minimal_managed_projection"
        )
    ):
        raise RuntimeError(
            "financial_semantic_minimal_managed_profile_identity_mismatch"
        )
    catalog = payload["decision_reason_catalog"]
    if (
        not isinstance(catalog, dict)
        or catalog.get("catalog_id") != DECISION_REASON_CATALOG_ID
        or catalog.get("semantic_version")
        != MINIMAL_MANAGED_DECISION_REASON_CATALOG_VERSION
        or catalog.get("managed_asset_family_id")
        != MANAGED_ASSET_FAMILY_ID
        or catalog.get("runtime_activation") is not False
        or not isinstance(catalog.get("reasons"), list)
    ):
        raise RuntimeError(
            "financial_semantic_minimal_managed_reason_catalog_identity_mismatch"
        )
    material = copy.deepcopy(catalog)
    supplied_integrity = material.pop("integrity_sha256", None)
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    reason_codes = [
        item.get("code")
        for item in catalog["reasons"]
        if isinstance(item, dict)
    ]
    if (
        len(canonical)
        != MINIMAL_MANAGED_DECISION_REASON_CATALOG_CANONICAL_SEMANTIC_BYTES
        or hashlib.sha256(canonical).hexdigest()
        != MINIMAL_MANAGED_DECISION_REASON_CATALOG_INTEGRITY_SHA256
        or supplied_integrity
        != MINIMAL_MANAGED_DECISION_REASON_CATALOG_INTEGRITY_SHA256
        or reason_codes
        != [
            "no_registry_type",
            "single_registry_type_no_safe_record",
            "ambiguous_registry_type",
        ]
    ):
        raise RuntimeError(
            "financial_semantic_minimal_managed_reason_catalog_integrity_mismatch"
        )
    return payload



def load_gate2_financial_semantic_model_assets(
    *,
    profile: str = "active",
) -> dict[str, Any]:
    """Return one exact closed-world managed-asset projection profile."""

    pack = _verified_pack()
    prompt_content = _verified_prompt()
    managed_assets = _verified_identities()
    active_assets = {
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
    if profile == "active":
        return active_assets
    if profile == "context_v2_candidate":
        return _context_v2_candidate_assets(
            active_pack=active_assets["semantic_pack"],
        )
    if profile == "minimal_model_surface_v1_candidate":
        return _minimal_managed_projection_assets(
            full_pack=pack,
        )
    raise RuntimeError("financial_semantic_model_asset_profile_unknown")


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
