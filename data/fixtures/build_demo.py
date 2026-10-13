"""Regenerate the checked-in synthetic fixture only; no network or real institutions."""
from hashlib import sha256
import json
from pathlib import Path

YEAR = 2027
AS_OF = "2026-09-30"
RULESET = "DEMO_M0_v1"


def build():
    institutions = [
        {"id": "DEMO_CN_INSTITUTE", "name": "DEMO_国内示例学院", "country": "CN", "is_synthetic": True},
        {"id": "DEMO_GB_INSTITUTE", "name": "DEMO_英国示例学院", "country": "GB", "is_synthetic": True},
    ]
    documents = []
    offerings = []

    def evidence(key, country, text, offering_id):
        identifier = f"DEMO_EVIDENCE_{key}"
        document = f"DEMO 合成招生测试资料。不是任何真实学校的官方依据。\n{text}"
        item = {
            "id": identifier, "offering_ids": [offering_id], "title": f"DEMO_{key}_合成依据", "is_synthetic": True,
            "source_url": f"demo://catalog/{key.lower()}", "document_version_id": f"DEMO_DOC_{key}_v1",
            "document_sha256": sha256(document.encode("utf-8")).hexdigest(),
            "locator": "section:synthetic_requirements", "excerpt": text, "entry_year": YEAR,
            "country": country, "province": "浙江" if country == "CN" else None,
            "applicant_category": "cn_mainland", "pathway": "gaokao" if country == "CN" else "uk_undergraduate",
            "review_status": "demo_reviewed", "data_as_of": AS_OF,
        }
        documents.append({"evidence": item, "raw_document": document})
        return identifier

    def rule(offer_id, suffix, field, minimum, evidence_id, scale, unit="points", deferral=None, stage="application"):
        return {"id": f"{offer_id}_{suffix}", "offering_id": offer_id, "field": field,
                "op": "gte", "value": minimum, "unit": unit, "scale": scale,
                "stage": stage, "evidence_id": evidence_id, "review_status": "demo_reviewed",
                "version": RULESET, "deferral": deferral}

    def offering(identifier, country, title, rules, deadline=None, deadline_evidence_id=None):
        institution = institutions[0 if country == "CN" else 1]
        offerings.append({"id": identifier, "institution_id": institution["id"],
                          "institution_name": institution["name"], "title": f"DEMO_{title}",
                          "is_synthetic": True, "country": country, "study_level": "bachelor", "entry_year": YEAR,
                          "province": "浙江" if country == "CN" else None, "applicant_category": "cn_mainland",
                          "course_system": "gaokao", "pathway": "gaokao" if country == "CN" else "uk_undergraduate",
                          "deadline": deadline, "deadline_evidence_id": deadline_evidence_id,
                          "deadline_status": "known" if deadline else "not_published", "rules": rules})

    cn = "DEMO_CN_MATH"
    cn_evidence = evidence("CN_MATH", "CN", "2027入学，浙江普通高考、中国内地申请人、本科：选考物理；实得高考总分至少560/750 points，实得数学至少100/150 points。本演示项目未公布申请截止日期。", cn)
    cn_rules = [rule(cn, "TOTAL", "assessments.gaokao_total", 560, cn_evidence, 750),
                rule(cn, "MATH", "assessments.math", 100, cn_evidence, 150),
                {"id": f"{cn}_SUBJECT", "offering_id": cn, "field": "subjects", "op": "in", "value": ["physics"],
                 "unit": None, "scale": None, "stage": "application", "evidence_id": cn_evidence,
                 "review_status": "demo_reviewed", "version": RULESET, "deferral": None}]
    offering(cn, "CN", "数学与计算本科示例", cn_rules)

    deferred = "DEMO_GB_DEFERRED"
    gb_evidence = evidence("GB_DEFERRED_REQUIREMENTS", "GB", "2027英国本科演示项目，中国内地普通高考申请人：实得高考总分至少600/750 points，入学阶段实得英语语言至少6.5/9 band。", deferred)
    policy = evidence("GB_DEFERRED_POLICY", "GB", "2027本演示课程允许申请时缺少英语语言成绩，入学前必须取得至少6.5/9 band，并于2027-08-20之前后补。此政策仅属合成演示，不是真实学校政策。", deferred)
    deadline = evidence("GB_DEFERRED_DEADLINE", "GB", "2027本演示课程语言后补截止日期为2027-08-20；仅提供日期，没有截止时间或时区。", deferred)
    app_deadline = evidence("GB_APPLICATION_DATE", "GB", "2027本演示课程申请截止日期为2027-01-15；仅提供日期，没有截止时间或时区。", deferred)
    deferral = {"evidence_id": policy, "deadline": "2027-08-20", "deadline_evidence_id": deadline}
    offering(deferred, "GB", "英语可后补本科示例",
             [rule(deferred, "TOTAL", "assessments.gaokao_total", 600, gb_evidence, 750),
              rule(deferred, "LANGUAGE", "assessments.english_language", 6.5, gb_evidence, 9, "band", deferral, "enrollment")],
             "2027-01-15", app_deadline)

    no_policy = "DEMO_GB_NO_DEFERRAL"
    no_evidence = evidence("GB_NO_DEFERRAL", "GB", "2027英国本科演示项目，中国内地普通高考申请人：实得高考总分至少580/750 points，实得英语语言至少6.5/9 band；没有已审核的语言后补政策。申请截止日期未公布。", no_policy)
    offering(no_policy, "GB", "无语言后补政策本科示例", [
        rule(no_policy, "TOTAL", "assessments.gaokao_total", 580, no_evidence, 750),
        rule(no_policy, "LANGUAGE", "assessments.english_language", 6.5, no_evidence, 9, "band")])

    no_deadline = "DEMO_GB_MISSING_DEADLINE"
    missing_evidence = evidence("GB_MISSING_DEADLINE", "GB", "2027英国本科演示项目，中国内地普通高考申请人：实得高考总分至少580/750 points，入学阶段实得英语语言至少6.5/9 band。文字提及可后补，但未公布后补期限，因此不能构成可执行后补政策。申请日期也未公布。", no_deadline)
    offering(no_deadline, "GB", "后补期限未知本科示例", [
        rule(no_deadline, "TOTAL", "assessments.gaokao_total", 580, missing_evidence, 750),
        rule(no_deadline, "LANGUAGE", "assessments.english_language", 6.5, missing_evidence, 9, "band", stage="enrollment")])
    return {"is_synthetic": True, "data_as_of": AS_OF, "ruleset_version": RULESET,
            "institutions": institutions, "documents": documents, "offerings": offerings}


if __name__ == "__main__":
    destination = Path(__file__).with_name("demo_catalog.json")
    destination.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {destination} (synthetic only)")
