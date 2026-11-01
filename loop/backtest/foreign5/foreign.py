# -*- coding: utf-8 -*-
"""외국계 기관·펀드 제출인 판별 사전 (2026-09-08 고정).
포함: 글로벌 자산운용사·연기금·국부펀드·헤지펀드·외국계 IB.
제외: 한국 기업이지만 라틴문자 사명(HLB·NICE·BGF·FSN·SNT 등), 한국계 캐피탈·PEF(한앤코·스틱 등).
"""
import re
FOREIGN = re.compile(
    r'MORGANSTANLEY|MORGAN\s?STANLEY|J\.?P\.?MORGAN|JPMorgan|BlackRock|블랙록'
    r'|FILLIMITED|Fidelity|피델리티'
    r'|CapitalResearch|CapitalGroup|캐피탈그룹|캐피탈리서치'
    r'|GICPrivate|GOVERNMENTOFSINGAPORE|Temasek|테마섹'
    r'|NorgesBank|노르게스|Wellington|웰링턴'
    r'|Kopernik|Orbis|FederatedHermes|Silchester|SwedbankRobur'
    r'|UBSAG|UBS\s?AG|GOLDMANSACHS|GoldmanSachs|골드만'
    r'|T\.?RowePrice|티로우프라이스|Invesco|인베스코'
    r'|Schroder|슈로더|슈뢰더|Templeton|템플턴|Aberdeen|애버딘'
    r'|BaillieGifford|베일리기포드|AllianceBernstein|얼라이언스번스타인'
    r'|FranklinResources|프랭클린|Amundi|아문디|Eastspring|이스트스프링'
    r'|Vanguard|뱅가드|StateStreet|스테이트스트리트|Nomura|노무라'
    r'|Citigroup|CreditSuisse|DeutscheBank|HSBC|BNPParibas'
    r'|Elliott|엘리엇|Dalton|달튼|Whitebox|화이트박스|OakTree|오크트리'
    r'|APG|MiriCapital|APSAsset|APS\b'
    r'|BlackstoneKKR|Blackstone|블랙스톤|KKR|Carlyle|칼라일|Bain\s?Capital'
    r'|Affinity|어피니티|NHPEA|Highland', re.IGNORECASE)

# 오탐 방지 — 아래는 한국 법인이므로 무조건 제외
EXCLUDE = re.compile(r'^(HLB|NICE|BGF|FSN|SNT|APS)(\b|홀딩스|생명과학|제넥스|$)'
                     r'|SBI인베스트먼트|BNK투자증권|MDS스피어|DSC인베스트먼트|NuriFlex|MSEED'
                     r'|무림캐피탈|한앤코|한앤브라더스|신한캐피탈|미래에셋캐피탈|스틱|캐피탈제\d'
                     r'|엔비에이치캐피탈|제이비우리캐피탈|아이비케이캐피탈|오케이캐피탈|리캐피탈'
                     r'|케이던스캐피탈|투자조합')

def is_foreign(name):
    if EXCLUDE.search(name):
        return False
    return bool(FOREIGN.search(name))
