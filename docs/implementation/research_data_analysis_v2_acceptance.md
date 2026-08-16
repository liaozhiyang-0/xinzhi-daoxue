# RESEARCH_03_DATA_ANALYSIS_V2 闃舵楠屾敹璁板綍

## 褰撳墠鐘舵€?
鏈樁娈靛凡瀹屾垚鏈湴 v2 鍚堝悓銆佽川閲忛棬绂併€佸垎鏋愯鍒掑喕缁撱€佸洓绫?MVP 鎵ц銆佸鏉傝璁℃墿灞曘€乆LSX/Parquet 鍙楁帶璇诲彇銆丅ootstrap/Holm 绋冲仴鎬ц緭鍑恒€丼VG Artifact銆佷汉宸ュ鏍哥瀛楁搷浣溿€乀askRunner 鏈湴鍒嗘敮鍜岀粨鏋滄不鐞嗛€傞厤銆傚晢涓氬寲鎴愮啛搴︺€佺湡瀹炵爺绌惰€呭鐜扮巼鍜屽閮ㄥ競鍦鸿瘉鎹粛寰呰ˉ锛屼笉灏嗗悎鎴愭祴璇曠粨鏋滃啓鎴愮湡瀹炴晥鏋溿€傚叏閲忓洖褰掑凡鎸夋祴璇曟枃浠跺垎鐗囨墽琛岋紱绉戠爺鍒嗘瀽鍙婂叾渚濊禆閾鹃€氳繃锛屽墿浣欓樆鏂槑纭褰曚负鏃㈡湁鏉愭枡婕傜Щ鎴栭暱鑰楁椂缁勫悎鐗囪秴鏃躲€?
鎴嚦 2026-08-08 鐨勮拷鍔犲璁¤繕淇浜嗕袱澶勮涔夎竟鐣岋細澶氱粍姣旇緝鐜板湪鎸夎姹備腑鐨?`multiple_comparison_method` 鍐冲畾鏄惁杈撳嚭 Holm 璋冩暣锛屼笖鏈湴 V2 缁撴灉涓嶅啀琚爣璁颁负浜戠鎵ц銆傝拷鍔犲畾鍚戝洖褰掑凡閫氳繃锛涢噸杞藉悗鐨?8000 绔彛鐪熷疄 HTTP 鍐掔儫涔熺‘璁?`cloud_status=not_requested`銆乣model_calls=0`锛屽苟纭 `none` 绛栫暐鍙緭鍑烘湭璋冩暣鎴愬姣旇緝涓斾繚鐣欎汉宸ュ鏍搞€?
## 宸插畬鎴愭枃浠?
- `apps/api/app/contracts/research_analysis.py`
- `apps/api/app/contracts/__init__.py`
- `apps/api/app/services/research_data_quality.py`
- `apps/api/app/services/research_analysis_planner.py`
- `apps/api/app/services/research_analysis_review.py`
- `apps/api/app/services/research_local_analysis.py`
- `analysis_provenance.json`锛堢敱鏈湴鎵ц鍣ㄥ湪浠诲姟 Artifact 鐩綍鐢熸垚锛?- `apps/api/app/services/research_tabular_io.py`
- `apps/api/app/core/config.py`
- `apps/api/app/services/internal_agent_execution.py`
- `apps/api/app/services/agent_result_governance.py`
- `apps/api/app/services/task_runner.py`
- `apps/api/app/api/v1/tasks.py`
- `apps/api/pyproject.toml`
- `apps/api/app/static/debug/workspace.html`
- `apps/api/app/static/debug/workspace.js`
- `apps/api/app/static/debug/workspace-v2.css`
- `scripts/team_launcher.py`
- `scripts/run_e2e_soak.py`
- `apps/api/tests/test_research_analysis_contract.py`
- `apps/api/tests/test_research_data_quality.py`
- `apps/api/tests/test_research_analysis_planner.py`
- `apps/api/tests/test_research_local_analysis.py`
- `apps/api/tests/test_research_analysis_review.py`
- `apps/api/tests/test_internal_agent_execution.py`
- `apps/api/tests/test_agent_result_governance.py`
- `apps/api/tests/test_xingchen_cloud_policy.py`
- `apps/api/tests/test_research_analysis_demo.py`
- `apps/api/tests/test_debug_page.py`
- `docs/architecture/research_data_analysis_v2.md`
- `docs/evaluation/research_data_analysis_v2_synthetic.md`
- `docs/commercial_cases/research_data_workbench_v1.md`
- `docs/implementation/research_data_analysis_v2_evidence_matrix.md`
- `docs/implementation/research_data_analysis_v2_completion_audit.md`
- `scripts/research_analysis_demo.py`
- `docs/implementation/research_analysis_pilot_input_template.md`
- `scripts/validate_research_pilot.py`
- `apps/api/tests/test_validate_research_pilot.py`

## 宸叉墽琛岄獙璇?
| 楠岃瘉 | 缁撴灉 |
| --- | --- |
| v2 瀹氬悜鍚堝悓/璐ㄩ噺/璁″垝/鎵ц銆佽矾鐢便€佹不鐞嗗拰鍓嶇濂戠害娴嬭瘯 | 閫氳繃锛涙渶缁堝畾鍚戝洖褰?49 椤归€氳繃锛? 涓緷璧栧純鐢ㄨ鍛婏紱瑕嗙洊鍓嶇璧勬簮鐗堟湰銆佸満鏅粦瀹氥€乂2 鍚堝悓/璐ㄩ噺/璁″垝/鎵ц銆佹不鐞嗗拰鏄熻景闅旂 |
| API 鏄熻景閰嶇疆杈圭晫涓庡彈鎺ч檮浠跺啋鐑?| 閫氳繃锛沗scene=dispatch`銆乣scenario_id=research_data_workbench_v1` 涓婁紶 CSV 鍚?v2 浠诲姟瀹屾垚锛孭rovider 璋冪敤鏁颁负 0锛岀敤鎴疯緭鍑虹洰褰曟湭琚娇鐢紝Artifact 涓庝复鏃剁洰褰曞潎鍙楅厤缃拰浠诲姟 ID 闅旂 |
| 娴忚鍣?`/workspace`銆乣/demo`銆乣/workspace?scenario_id=research_data_workbench_v1&analysis_v2=1` | 椤甸潰鍔犺浇瀹屾垚锛沄2 闈㈡澘鍙銆侀粯璁や袱缁勫疄楠屾瘮杈冦€侀棶棰樺弬鏁拌浇鍏ワ紝鏂板 estimand/鍒嗘瀽鍗曚綅/鍗忚/鏂规硶璇佹嵁鎺т欢鍙锛涙祻瑙堝櫒璁″垝鎻愪氦鍐掔儫瀹屾垚锛屾帶鍒跺彴鏃?error/warning |
| 鏈疆鐪熷疄 API V2 鎻愪氦 | 閫氳繃锛涙湰鍦?`POST /api/v1/tasks` 璁″垝鎬佷换鍔¤繑鍥?`completed`锛孉gent 涓?`RESEARCH_03_DATA_ANALYSIS_V1`锛岀粨鏋勫寲缁撴灉鏍囪 `analysis_v2=true`銆乣status=insufficient_data`锛涙湰杞湭璋冪敤鏄熻景 |
| 鍓嶇鏍稿績璧勬簮 | 宸ヤ綔鍙?HTML銆並aTeX銆乽i-core銆亀orkspace銆乨esign tokens銆乻hell銆乧omponents銆亀orkspace-v2 鍧囧疄闄呰繑鍥?200锛沄2 鐩稿叧 JS/CSS 浣跨敤 `20260808-research-analysis-v10` 缂撳瓨鐗堟湰锛涙柊澧?estimand銆佸垎鏋愬崟浣嶃€佸崗璁憳瑕併€佹帰绱㈡€?楠岃瘉鎬у拰鏂规硶璇佹嵁鍏ュ彛 |
| Ruff | 閫氳繃锛沗ruff check apps/api/app apps/api/tests scripts/validate_config.py scripts/validate_scenarios.py scripts/validate_commercial_scenarios.py scripts/validate_external_sources.py` |
| Mypy | 閫氳繃锛涙湰杞疄闄呮墽琛?`mypy apps/api/app --no-incremental`锛?53 涓簮鏂囦欢鏃犻棶棰?|
| 閰嶇疆鏍￠獙 | `scripts/validate_config.py` 閫氳繃 |
| 鏁忔劅鏂囦欢鎵弿 | `scripts/check_sensitive_files.py` 閫氳繃 |
| 鍟嗕笟鍦烘櫙銆佸満鏅洰褰曘€佸閮ㄦ潵婧愭牎楠?| 閫氳繃锛? 涓晢涓氬満鏅潎涓?synthetic 涓旇姹備汉宸ュ鏍?|
| 椤圭洰绾?`scripts/check.ps1` | 鏈畬鎴愶細閰嶇疆銆佹晱鎰熸枃浠躲€丷uff銆丮ypy 宸叉墽琛岋紱鍏跺唴閮ㄥ叏閲?Pytest 鍦?10 鍒嗛挓鍐呮湭缁撴潫锛岃剼鏈瓒呮椂缁堟 |
| 鍏ㄩ噺 Pytest 鍒嗙墖 | 宸插彇寰楀ぇ閮ㄥ垎鍙鏍哥粨鏋滐細鐭ヨ瘑/瀛︿範/妯″瀷鐗?`107 passed, 2 skipped`锛涘妯℃€?缂栨帓/RAG 鐗?`56 passed, 2 skipped`锛涚鐮?鍦烘櫙/SSE 鐗?`66 passed`锛涗换鍔?宸ヤ綔娴佺墖 `130 passed`锛涘晢涓氭渚?澶栭儴妫€绱?绉戠爺鍒嗘瀽鐗?`111 passed`锛涙鍓嶈绋嬭祫浜?璇勬祴鐗?`121 passed, 3 failed, 2 skipped`銆傚け璐ヤ负姣旇禌鍖呮竻鍗曞綋鍓嶅啓鍏?`demo_cases_included: true`銆佺绾胯瘎娴嬫姤鍛婂綋鍓嶅寘鍚?82 涓渚嬭€屾祴璇曚粛瑕佹眰绌烘憳瑕侊紝浠ュ強灏辩华瀹¤鐢卞悓涓€鏉愭枡婕傜Щ瑙﹀彂 `review`銆傛暀瀛?鍓嶇澶х粍鍚堢墖鍦?10 鍒嗛挓鍐呮湭缁撴潫涓旀棤澶辫触鎽樿锛屼笉鑳藉绉板叏閲忛€氳繃 |
| 鏈疆 Mypy 澶嶆牳 | 宸插畬鎴愶紱`mypy apps/api/app --no-incremental` 杩斿洖 `Success: no issues found in 253 source files` |
| 鍓嶇鑴氭湰璇硶 | `node --check apps/api/app/static/debug/workspace.js` 閫氳繃 |
| 鏈疆杩愯鎬佸墠绔?API V2 缁撴灉鎽樿 | 閫氳繃锛涙墽琛?`team_launcher.py start --port 8000 --reload --force-reload` 鍚庯紝鐪熷疄 HTTP 璧勬簮鍧囪繑鍥?200锛屼换鍔″畬鎴愬苟杩斿洖 `RESEARCH_03_DATA_ANALYSIS_V1`銆乸rovenance dataset/checksum銆乣source_ref_included=false` 鍜屾柟娉曡瘉鎹紩鐢?|
| 鏈疆澶嶆潅鍒嗘瀽涓庢牸寮忓洖褰?| 鍘嗗彶瀹氬悜鍥炲綊 36 椤归€氳繃锛涜拷鍔犳湰鍦版墽琛屽櫒 12 椤归€氳繃銆佺鐮斿垎鏋愪緷璧栭摼 38 椤归€氳繃锛岃鐩栧疄闄?XLSX銆丳arquet銆佸缁勬瘮杈冦€侀噸澶嶆祴閲忋€丅ootstrap銆丠olm銆丼VG Artifact銆乸rovenance 鍜岀瀛楁寔涔呭寲 |
| 鍙楁帶闄勪欢 HTTP 杈圭晫 | `test_xingchen_cloud_policy.py` 6 椤归€氳繃锛涢噸杞藉悗鐨勭湡瀹?HTTP 澶氱粍 CSV 鍐掔儫閫氳繃锛岀‘璁?`provider=local_analysis_v2`銆乣cloud_status=not_requested`銆乣model_calls=0`锛屽苟鐢熸垚 7 涓垎鏋?Artifact |
| 鍥涚被 MVP 鍙鐜版紨绀?| 閫氳繃锛沗scripts/research_analysis_demo.py --output-root <鐩綍>` 鐢熸垚鍥涚被鍚堟垚杈撳叆銆佷换鍔＄骇 Artifact 鍜?`demo_manifest.json`锛涘疄娴嬪洓绫诲潎涓?`executed`銆佺綉缁滆皟鐢?0銆佷粛瑕佹眰浜哄伐澶嶆牳 |
| 鏁版嵁 provenance 涓庤矾寰勮劚鏁?| 閫氳繃锛涙瘡涓垚鍔熷垎鏋愬寘鐢熸垚 `analysis_provenance.json`锛岃褰曟暟鎹増鏈?鏍煎紡/琛屽垪鏁?checksum/鍙橀噺/鐜锛屾槑纭笉鍐欏叆鏈湴 `source_ref`锛沚undle 鍜?report 鍚屾寮曠敤璇?provenance |
| 鎺堟潈璇曠偣鏉愭枡棰勬 | 閫氳繃锛沗validate_research_pilot.py --request-json <鏂囦欢> --check-data` 妫€鏌ュ悎鍚屻€佽川閲忛棬绂併€乧hecksum 鍜屽舰鐘讹紝涓嶈皟鐢ㄦā鍨嬫垨澶栭儴妫€绱?|
| V2 Task API provenance 鍥炲綊 | 閫氳繃锛沗test_task_api.py` 6/6 閫氳繃锛孉PI 绾у垱寤?杞娴嬭瘯鍚屾椂鏂█鐢ㄦ埛鏂囧瓧涓?CSV 鍦烘櫙缁戝畾鍚庝粛璺敱鍒?`RESEARCH_03_DATA_ANALYSIS_V1`锛屾棤鏂囦欢鐨勭敤鎴锋枃瀛楀満鏅篃杩斿洖鏈湴 V2 璁″垝锛宔stimand 杩涘叆鍐荤粨璁″垝銆乽nit of analysis 杩涘叆 provenance銆乵ethod reference ID 杩涘叆缁撴灉锛屼笖纭 checksum 鍜岃矾寰勮劚鏁?|
| 鏈疆浠诲姟 API/SSE/鍓嶇鎵╁睍鍥炲綊 | 閫氳繃锛?5 椤归€氳繃锛岃鐩栦换鍔?API銆侀潪闃诲鍒涘缓銆丼SE 椤哄簭/閲嶈繛銆丱penAPI銆佸唴閮ㄦ墽琛屽櫒銆佸鏍告湇鍔″拰鍓嶇椤甸潰濂戠害锛沗node --check` 閫氳繃 |
| 鍓嶇鍙楁帶鏍煎紡涓庝細璇濋殧绂昏ˉ涓?| 閫氳繃锛涙祻瑙堝櫒渚?CSV/TSV/JSON/XLSX/Parquet 鏁版嵁鏂囦欢涓?PDF/DOC/DOCX/TXT/MD/鍥剧墖杈呭姪鏉愭枡鍏ュ彛宸蹭笌鏈嶅姟绔悓姝ワ紝缁撴瀯鍖栭檮浠惰嚜鍔ㄧ敓鎴愬彈鎺?manifest 骞跺惎鐢ㄦ湰鍦版墽琛岋紱浠诲姟鍒涘缓鍓嶇疆鏌ヨ鎸夋湁鏁堢敤鎴疯繃婊わ紝浠诲姟 API 鍥炲綊鏂板璺ㄧ敤鎴?session 璁块棶鎷掔粷 |
| 鐢ㄦ埛缁撴灉灞曠ず杈圭晫 | 閫氳繃锛涙櫘閫氭暟鎹垎鏋愮瓟妗堜笉灞曠ず鍐呴儴鈥滃垎鏋愭楠も€濆拰鈥滃鐜拌姹傗€濓紝瀹¤ Artifact 浠嶄繚鐣欑粨鏋勫寲瀛楁 |

## 閲嶈杈圭晫

1. `execute=false` 鍙喕缁撹鍒掞紝涓嶈鍙栧師濮嬫暟鎹€?2. `execute=true` 蹇呴』鎻愪緵鎺堟潈 manifest銆乧hecksum銆佹暟鎹瓧鍏搞€佸彉閲忚鑹插拰宸茬櫥璁伴檮浠讹紱杈撳嚭鐩綍鐢?`RESEARCH_ANALYSIS_ARTIFACT_ROOT` 閰嶇疆锛屼复鏃剁洰褰曠敱 `RESEARCH_ANALYSIS_TEMP_ROOT` 閰嶇疆銆?3. 鎵ц鍣ㄦ敮鎸佹湰鍦?CSV/TSV/JSON/XLSX/Parquet锛涚己灏戝彲閫夋牸寮忎緷璧栨垨澹版槑鏍煎紡涓嶅彈鏀寔鏃剁洿鎺ュけ璐ワ紝涓嶉潤榛樼寽娴嬨€?4. 璁烘枃鍙彲閫氳繃 `method_reference` 杩涘叆鏂规硶璇佹嵁 ID锛涗笉鑳芥浛浠ｇ敤鎴锋暟鎹€?5. 鎵€鏈夋垚鍔熸墽琛岀粨鏋滀粛甯?`human_review_required=true`锛屼笉鑳戒綔涓鸿嚜鍔ㄥ彂琛ㄧ粨璁恒€?6. 榛樿 V1銆丼olver 鍐荤粨鍩虹嚎鍜岀鐮旀绱㈣矾寰勬病鏈夎鏀瑰啓锛泇2 浠呯敱鏄惧紡 `options.research_analysis_v2` 鍚敤銆?
## 鍚庣画楠屾敹闂ㄦ

- 澶勭悊姣旇禌鍖呮竻鍗?绂荤嚎璇勬祴鎶ュ憡涓や釜鏃㈡湁鏉愭枡闃绘柇鍚庨噸鏂拌繍琛?`scripts/check.ps1`锛?- 瀵规暀瀛?鍓嶇澶х粍鍚堢墖缁х画鎸夋洿灏忔枃浠剁粍鎷嗗垎锛岄伩鍏?10 鍒嗛挓缁勫悎瓒呮椂骞跺彇寰楅€愭枃浠剁粨鏋滐紱
- 涓虹湡瀹炴巿鏉冭瘯鐐硅ˉ鍏呮暟鎹瓧鍏搞€佺爺绌跺崗璁€侀殣绉?浼︾悊鏉愭枡銆佹柟娉曟潵婧愬拰澶嶇幇鏃ュ織锛?- 浠ユ巿鏉冭瘯鐐归獙璇佺湡瀹炲鏉傝璁°€佸鐜版棩蹇椼€侀殣绉?浼︾悊娴佺▼鍜屽鏌ョ瀛楃殑涓氬姟浣跨敤锛涘綋鍓嶄唬鐮佽矾寰勫拰鍚堟垚鍥炲綊宸茶鐩栧熀纭€鎵╁睍锛?- 缁х画鎵╁睍鏇村鏉傜殑閲嶅娴嬮噺銆佸鍥犲瓙璁捐銆侀暱鏈熷鏌ョ暀瀛樺拰鍥惧舰瀹￠槄鎿嶄綔锛涘綋鍓嶅墠绔凡鏄剧ず V2 鐘舵€佹憳瑕併€佽川閲忛棬绂併€佽瘖鏂€佺ǔ鍋ユ€с€佽瘉鎹拰澶嶆牳鐘舵€侊紝涓嶅啀鍙緷璧栭€氱敤 sections锛?- 鍦ㄤ笉姹℃煋浼氳瘽鍜屼笉鏀瑰彉 Solver 鐨勫墠鎻愪笅缁х画杩愯鐪熷疄鏈湴 API/鍓嶇闀块摼璺獙鏀讹紱鏈疆宸插畬鎴愪竴娆¤鍒掓€侀摼璺紝甯︾湡瀹炴巿鏉冩暟鎹殑鎵ц鎬佷粛闇€鐙珛璇曠偣鏉愭枡銆?
