/**
 * build_report_docx.js — 루프 엔지니어링 보고서를 표준 docx 양식으로 생성.
 * 양식 기준: 루프엔지니어링_2026-06-19_sonnet_확장187종.docx
 *
 * 사용법: node build_report_docx.js report.json output.docx
 * report.json 구조는 본 파일 하단 주석 참조.
 */
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType,
} = require("docx");

const [, , inPath, outPath] = process.argv;
const data = JSON.parse(fs.readFileSync(inPath, "utf-8"));

const TABLE_WIDTH = 9360;
const cellBorder = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const cellBorders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
const tableBorder = { style: BorderStyle.SINGLE, size: 4, color: "auto" };
const tableBorders = { top: tableBorder, bottom: tableBorder, left: tableBorder, right: tableBorder, insideHorizontal: tableBorder, insideVertical: tableBorder };
const cellMargins = { top: 80, bottom: 80, left: 120, right: 120 };

function bodyPara(text) {
  return new Paragraph({ spacing: { after: 120 }, children: [new TextRun(text)] });
}
function heading1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
}
function bulletLine(text) {
  return new Paragraph({ spacing: { after: 80 }, children: [new TextRun(`• ${text}`)] });
}
function makeTable(headers, rows, widths) {
  const w = widths || headers.map(() => Math.floor(TABLE_WIDTH / headers.length));
  const headerRow = new TableRow({
    children: headers.map((h, i) => new TableCell({
      borders: cellBorders, width: { size: w[i], type: WidthType.DXA },
      shading: { fill: "D5E8F0", type: ShadingType.CLEAR }, margins: cellMargins,
      children: [new Paragraph({ children: [new TextRun({ text: h, bold: true })] })],
    })),
  });
  const dataRows = rows.map((r) => new TableRow({
    children: r.map((c, i) => new TableCell({
      borders: cellBorders, width: { size: w[i], type: WidthType.DXA }, margins: cellMargins,
      children: [new Paragraph({ children: [new TextRun(String(c))] })],
    })),
  }));
  return new Table({
    width: { size: TABLE_WIDTH, type: WidthType.DXA },
    columnWidths: w,
    borders: tableBorders,
    rows: [headerRow, ...dataRows],
  });
}

const children = [];

// 제목 + 부제
children.push(new Paragraph({ children: [new TextRun({ text: data.title, bold: true, size: 30 })] }));
children.push(new Paragraph({ children: [new TextRun(data.subtitle)] }));

// 요약
children.push(heading1("요약"));
data.summary.forEach((s) => children.push(bulletLine(s)));

// 유니버스 범위
if (data.universeNote) {
  children.push(heading1("유니버스 범위 (중요)"));
  children.push(bodyPara(data.universeNote));
}

// (A) 현 추천 채점
children.push(heading1(data.sectionA.heading));
children.push(makeTable(data.sectionA.tableHeaders, data.sectionA.tableRows, data.sectionA.colWidths));
children.push(bodyPara(""));
data.sectionA.notes.forEach((n) => children.push(bodyPara(n)));

// Reference — 유니버스 상위 1~5위 (항상 표시, 참고용 · 추천 선정에는 미사용)
// (A2) 조합제 shadow 병기 — 통합 루프 필수 섹션 (report-format.md 2026-07-26 추가)
if (data.sectionA2) {
  children.push(heading1(data.sectionA2.heading));
  (data.sectionA2.intro || []).forEach((n) => children.push(bodyPara(n)));
  children.push(makeTable(data.sectionA2.tableHeaders, data.sectionA2.tableRows, data.sectionA2.colWidths));
  children.push(bodyPara(""));
  (data.sectionA2.notes || []).forEach((n) => children.push(bodyPara(n)));
}

if (data.referenceTop5) {
  children.push(heading1(data.referenceTop5.heading || "Reference — 유니버스 상위 1~5위 (참고용)"));
  if (data.referenceTop5.note) children.push(bodyPara(data.referenceTop5.note));
  children.push(makeTable(data.referenceTop5.tableHeaders, data.referenceTop5.tableRows, data.referenceTop5.colWidths));
  children.push(bodyPara(""));
}

// 원인 분석
children.push(heading1("원인 분석 (불가항력 vs 학습가능)"));
data.causeAnalysis.forEach((n) => children.push(bodyPara(n)));

// (B) 신규 방법 재산출
children.push(heading1(data.sectionB.heading));
data.sectionB.intro.forEach((n) => children.push(bodyPara(n)));
children.push(makeTable(data.sectionB.tableHeaders, data.sectionB.tableRows, data.sectionB.colWidths));
children.push(bodyPara(""));
data.sectionB.notes.forEach((n) => children.push(bodyPara(n)));

// 방법 변경 요약 · 교차검증 게이트
children.push(heading1(data.methodChange.heading));
data.methodChange.notes.forEach((n) => children.push(bodyPara(n)));

// 9절 데이터 검증 결과 (선택 — integrity 키가 있을 때만)
if (data.integrity) {
  children.push(heading1(data.integrity.heading || "9. 데이터 검증 결과"));
  (data.integrity.notes || []).forEach((n) => children.push(bodyPara(n)));
}

// 최종 채택
children.push(heading1("최종 채택"));
data.finalAdoption.forEach((s) => children.push(bulletLine(s)));

// 확인 문구 · 면책
children.push(heading1("확인 문구 · 면책"));
children.push(bodyPara(data.disclaimer));

const doc = new Document({
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outPath, buf);
  console.log("written:", outPath);
});

/* report.json 예시 구조:
{
  "title": "루프 엔지니어링 보고서 (Sonnet 버전) — 평가 대상일 2026년 6월 22일 (월)",
  "subtitle": "단기 추천 ETF 5종 채점 · 방법 개선 · 교차검증  |  채점 기준: ... | 유니버스 186종 | 적용 확정방법: v1.2 | 실행 모델: Claude Sonnet",
  "summary": ["...", "..."],
  "universeNote": "...",
  "sectionA": { "heading": "(A) 현 추천 채점 — ...", "tableHeaders": [...], "tableRows": [[...],...], "colWidths": [...], "notes": ["...", "..."] },
  "referenceTop5": { "heading": "Reference — 유니버스 상위 1~5위 (참고용)", "note": "...", "tableHeaders": ["순위","종목","코드","전일종가","당일종가","상승률"], "tableRows": [[...],...], "colWidths": [...] },
  "causeAnalysis": ["...", "..."],
  "sectionB": { "heading": "(B) 신규 방법(v1.x 잠정) 재산출 — ...", "intro": ["..."], "tableHeaders": [...], "tableRows": [[...]], "colWidths": [...], "notes": ["..."] },
  "methodChange": { "heading": "방법 변경 요약 (v1.x 잠정) · 교차검증 게이트", "notes": ["..."] },
  "finalAdoption": ["...", "..."],
  "disclaimer": "신규 추천(B)은 분석 방법(전날까지 정보)으로 산출했으며 상승률 결과를 보고 정렬하지 않았습니다(룩어헤드 금지). 본 자료는 정보 제공 목적이며 투자 자문이 아닙니다. 모든 투자 판단과 책임은 투자자 본인에게 있습니다."
}
*/
