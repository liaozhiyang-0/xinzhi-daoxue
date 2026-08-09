# RESEARCH_03_DATA_ANALYSIS_V2 璇佹嵁鐭╅樀涓庨闄╅棬绂?
鏈枃浠跺彧璁板綍褰撳墠浠撳簱涓凡缁忓彲澶嶆牳鐨勫伐绋嬭瘉鎹€傚悎鎴愭祴璇曘€侀潤鎬佹鏌ュ拰鏈湴鍐掔儫涓嶈兘鏇夸唬鐪熷疄鐮旂┒鑰呰瘯鐐广€佹巿鏉冩暟鎹垨澶栭儴甯傚満璧勬枡锛涚己灏戞潵婧愮殑椤圭洰缁熶竴鏍囪涓衡€滃緟琛ヨ瘉鎹€濄€?
## 璇佹嵁鐭╅樀

| 缁撹/鎵胯 | 褰撳墠璇佹嵁 | 楠岃瘉鏂瑰紡 | 褰撳墠鐘舵€?| 涓嶅緱澶栨帹 |
| --- | --- | --- | --- | --- |
| 鍏堝畾涔夌爺绌堕棶棰樸€佽璁°€佸彉閲忚鑹插拰缁撹杈圭晫 | `apps/api/app/contracts/research_analysis.py`銆乣research_analysis_planner.py` | 鍚堝悓涓庤鍒掑櫒娴嬭瘯 | 宸茶惤鍦?| 涓嶄唬琛ㄦ柟娉曢€傚悎鎵€鏈夊鏉傝璁?|
| 鏁版嵁璐ㄩ噺闂ㄧ鍦ㄨ绠楀墠鎵ц | `apps/api/app/services/research_data_quality.py`銆乣research_local_analysis.py` | 缂?manifest銆佹巿鏉冦€乧hecksum銆佸舰鐘跺拰鏈０鏄庣己澶辩瓥鐣ユ祴璇?| 宸茶惤鍦?| 鍙鏌ュ凡澹版槑鍏冩暟鎹紝涓嶈兘鏇夸唬鍘熷鏁版嵁瀹¤ |
| 鍥涚被 MVP 鍙湪鏈湴纭畾鎬ф墽琛?| `research_local_analysis.py`銆佸悎鎴?fixture | 涓ょ粍姣旇緝銆佽瀵熷洖褰掋€佹椂闂村簭鍒椼€佸皬鏍锋湰娴嬭瘯 | 宸茶惤鍦帮紙鍚堟垚杈撳叆锛?| 涓嶄唬琛ㄧ湡瀹炴暟鎹噯纭巼鎴栫鐮斿彂鐜?|
| 澶嶆潅璁捐涓庡閲嶆瘮杈冩湁鏄庣‘杈圭晫 | `research_analysis_planner.py`銆乣research_local_analysis.py` | 澶氱粍姣旇緝銆佸０鏄庡紡 `holm`/`none` 澶氶噸姣旇緝绛栫暐銆佹湭璋冩暣缁撴灉澶嶆牳鎻愮ず鍜岄噸澶嶉厤瀵归敭闃绘柇娴嬭瘯 | 宸茶惤鍦帮紙鍚堟垚杈撳叆锛涘畾鍚戝洖褰掗€氳繃锛?| 涓嶄唬琛ㄦ敮鎸佹墍鏈夊鍥犲瓙/绾靛悜璁捐 |
| Bootstrap 缁撴灉鍙鐜?| `research_analysis.py`銆乣research_local_analysis.py` | 鍥哄畾 `random_seed` 鐨勯噸澶嶆墽琛岀粨鏋滄瘮杈?| 宸茶惤鍦帮紙鍚堟垚杈撳叆锛?| 涓嶄唬琛ㄦ娊鏍锋満鍒舵垨鍖洪棿瑕嗙洊鐜囧凡鐢辩湡瀹炶瘯鐐归獙璇?|
| 杈撳嚭鍖呭惈璇婃柇銆佺ǔ鍋ユ€у拰浜哄伐澶嶆牳椤?| `research_analysis_review.py`銆佸垎鏋?bundle | 瀹氬悜 API 鍥炲綊涓?Artifact 鏍￠獙 | 宸茶惤鍦?| 涓嶄唬琛ㄤ笓瀹跺凡缁忕瀛?|
| 鍒嗘瀽鍖呰兘澶嶇幇鏁版嵁鐗堟湰涓斾笉娉勬紡鏈湴璺緞 | `research_local_analysis.py` 鐨?`analysis_provenance.json`銆乣analysis_bundle.json` | 鏍￠獙 dataset checksum銆佸彉閲忓畾涔夊拰 `source_ref_included=false`锛屽苟鏂█鏈湴 source_ref 涓嶅嚭鐜板湪鎶ュ憡 | 宸茶惤鍦帮紙鏈湴锛?| 鐪熷疄璇曠偣浠嶉渶鐙珛淇濆瓨鎺堟潈璁板綍鍜岃繍琛屾棩蹇?|
| 鐪熷疄璇曠偣鏉愭枡杩涘叆 API 鍓嶅彲棰勬 | `scripts/validate_research_pilot.py`銆佽瘯鐐硅緭鍏ユā鏉?| 鍚堝悓閿欒銆乧hecksum 閿欒鍜屾湰鍦版枃浠跺舰鐘舵祴璇曪紱棰勬鍣ㄤ笉璋冪敤缃戠粶鎴栫粺璁℃墽琛?| 宸茶惤鍦帮紙鏈湴锛?| 涓嶈兘鏇夸唬浼︾悊瀹℃壒銆佹暟鎹巿鏉冩垨缁熻甯堢瀛?|
| XLSX/Parquet 鍙楁帶杈撳叆 | `research_tabular_io.py`銆乣internal_agent_execution.py`銆乣pyproject.toml` | 瀹為檯 XLSX/Parquet 鍚堟垚鏂囦欢璇诲彇锛涚己渚濊禆鏃舵槑纭樆鏂?| 宸茶惤鍦帮紙鏈湴杩愯鏃讹級 | 涓嶄唬琛ㄤ换鎰?Excel 宸ヤ綔绨裤€佸鏉?schema 鎴栬秴澶ф枃浠跺潎宸叉敮鎸?|
| 浜哄伐澶嶆牳绛惧瓧鍙璁℃寔涔呭寲 | `POST/GET /api/v1/tasks/{task_id}/research-review`銆乣research_review_decision.json` | 娓呭崟瀹屾暣鍖归厤銆佺瀛?hash銆佷换鍔＄洰褰曢殧绂诲拰瓒婄晫娴嬭瘯 | 宸茶惤鍦帮紙鏈湴锛?| 灏氭湭鏇夸唬鏈烘瀯绾х數瀛愮绔犮€侀暱鏈熺暀瀛樺拰鏉冮檺瀹¤ |
| 璁烘枃妫€绱㈢粨鏋滀笌鐢ㄦ埛鏁版嵁鍒嗙 | `ResearchEvidenceReference.role`銆乀askRunner v2 鍒嗘敮 | 浠呭厑璁?method_reference 杩涘叆鏂规硶璇佹嵁锛涙槦杈伴厤缃祴璇?| 宸茶惤鍦?| 涓嶄唬琛ㄥ閮ㄨ鏂囩粨璁洪€傜敤浜庡綋鍓嶆暟鎹?|
| v2 涓嶈皟鐢ㄦ槦杈板钩鍙?| `internal_agent_execution.py`銆乣task_runner.py` | 閰嶇疆 Xingchen 鍚?provider call 鏂█涓?0 | 宸茶惤鍦?| 浠呭鏄惧紡 v2 鏈湴璺緞鎴愮珛 |
| 浠诲姟鍒涘缓淇濇寔闈為樆濉?| `/api/v1/tasks`銆乀askRunner submit | API 浠诲姟鍒涘缓涓庣姸鎬佽疆璇㈡祴璇?| 宸茶惤鍦?| 涓嶇瓑浜庢墍鏈夊悗鍙拌祫婧愰兘鏈夌敓浜х骇瀹归噺 |
| V2 Task API 鑳芥寔涔呭寲鑴辨晱 provenance | `apps/api/tests/test_task_api.py`銆乣tasks.py`銆佸唴閮ㄦ墽琛屽櫒 | API 绾у垱寤?杞鍥炲綊锛屼互鍙?`team_launcher.py start --port 8000 --reload --force-reload` 鍚庣殑鐪熷疄 HTTP 浠诲姟鍐掔儫锛屾柇瑷€璺敱 Agent銆乨ataset checksum 鍜岃矾寰勮劚鏁忓瓧娈?| 宸茶惤鍦帮紙TestClient + 鏈湴 HTTP锛?| 鐪熷疄绉戠爺缁撹浠嶉渶鎺堟潈鏁版嵁鍜屼汉宸ュ鏍?|
| 鐪熷疄 API 鎵ц鍙鍙栧彈鎺ч檮浠跺苟闅旂 Artifact | `config.py` 鐨?`RESEARCH_ANALYSIS_ARTIFACT_ROOT`/`TEMP_ROOT`銆乣internal_agent_execution.py`銆佹枃浠舵湇鍔°€乣test_xingchen_cloud_policy.py` | 鍙楁帶涓婁紶涓庝换鍔℃墽琛屽洖褰掕鐩?CSV銆乆LSX銆丳arquet锛涙柇瑷€鐢ㄦ埛 `output_dir` 鏈垱寤恒€丄rtifact 鎸?task id 钀界洏銆佷复鏃剁洰褰曟竻鐞嗭紝涓旈厤缃簡鏄熻景 Provider 鏃朵粛涓嶈皟鐢ㄤ簯绔?| 宸茶惤鍦帮紙API 鍙楁帶闄勪欢閾捐矾锛?| 灏氭湭瑕嗙洊澶嶆潅宸ヤ綔绨裤€佸绉熸埛闀挎湡鐣欏瓨鍜屾寮忔満鏋勭骇绛剧珷绛栫暐 |
| 鍓嶇鍙互鎻愪氦鍙楁帶 V2 璁″垝鍙傛暟骞舵樉绀虹粨鏋滄憳瑕?| `workspace.html`銆乣workspace.js`銆乣workspace-v2.css` | `/workspace` 璧勬簮 200銆侀〉闈㈠绾﹀拰 `node --check`锛涙憳瑕佹寜 `structured_result.analysis_v2` 鏄剧ず璁捐/璐ㄩ噺/璇婃柇/绋冲仴鎬?璇佹嵁/澶嶆牳鐘舵€侊紝骞舵樉绀烘柟娉曟潵婧愩€佹暟鎹?provenance 涓庡彲澶嶇幇 Artifact 鏁伴噺锛涘墠绔畬鏁存敹闆?estimand銆佸垎鏋愬崟浣嶃€佸崗璁憳瑕併€佹帰绱㈡€?楠岃瘉鎬ф爣璁板拰鏂规硶璇佹嵁 JSON锛汣SV/TSV/JSON/XLSX/Parquet 鑷姩鐢熸垚鍙楁帶 `data_manifest` 骞跺惎鐢ㄦ湰鍦版墽琛岋紝鑷姩璇嗗埆鍒扮鐮旀暟鎹垎鏋愮殑鐢ㄦ埛闂涔熶細鍚敤 V2锛岀敤鎴烽棶棰樺悓姝ヨ繘鍏ョ爺绌惰姹傚拰 canonical 杈撳叆锛屾湭濉啓鐨勫疄楠屾瘮杈冨瓧娈垫寜闂涓庤〃澶磋ˉ榻愶紝PDF/DOC/DOCX/TXT/MD/鍥剧墖鍙綔涓鸿緟鍔╂潗鏂?| 宸查€氳繃椤甸潰濂戠害娴嬭瘯銆佷笂浼?CSV API 鍥炲綊銆佸満鏅粦瀹氱殑鐢ㄦ埛鏂囧瓧+CSV API 鍥炲綊銆佺湡瀹炴湰鍦?API/璧勬簮鍐掔儫鍜屾祻瑙堝櫒璁″垝鎻愪氦鍐掔儫 | 璧勬簮鐗堟湰 `20260808-research-analysis-v10` 鐢ㄤ簬閬垮厤鏃х紦瀛橈紱娌℃湁缁撴瀯鍖栦富鏁版嵁鏃朵粛鍙敓鎴愯鍒?|
| 鐢ㄦ埛缁撴灉闅愯棌鍐呴儴鎵ц缁嗚妭 | `agent_result_governance.py`銆乣internal_agent_execution.py`銆乣workspace.js` | 鏁版嵁鍒嗘瀽 renderer 涓嶅啀鍙戝竷 `analysis_steps` 涓?`reproducibility_requirements`锛涘墠绔啀鎸夊瓧娈靛睆钄芥棫 Agent 杩斿洖鐨勫悓鍚嶅瓧娈碉紱V2 Artifact 鍜屽唴閮ㄧ粨鏋勫寲缁撴灉浠嶄繚鐣欏璁″瓧娈?| 宸查€氳繃椤甸潰濂戠害鍜屼笂浼?CSV API 鍥炲綊 | 瀹¤鎺ュ彛浠嶅彲鑳借繑鍥炵粨鏋勫寲瀛楁锛屾櫘閫氱敤鎴风瓟妗堜笉灞曠ず |
| 鐢ㄦ埛鏂囧瓧涓庢暟鎹枃浠惰仈鍚堝垎鏋?| `workspace.js`銆乣router.py`銆乣test_task_router.py`銆乣test_task_api.py` | 鐢ㄦ埛闂鍚屾椂杩涘叆鐮旂┒璇锋眰鍜?canonical 杈撳叆锛汣SV/TSV/JSON 琛ㄥご鍙ˉ榻愬疄楠屾瘮杈冩墍闇€鍙橀噺瑙掕壊锛涘満鏅粦瀹氱殑 V2 璇锋眰鍦ㄦ棤浜戠妯″瀷瀵嗛挜鏃朵粛淇濇寔鏈湴 Agent锛屼笉闄嶇骇涓衡€滃伐浣滄祦灏氭湭鍙戝竷鈥?| 宸查€氳繃鍦烘櫙缁戝畾鐢ㄦ埛鏂囧瓧+CSV API 鍥炲綊鍜屾棤妯″瀷瀵嗛挜璺敱鍥炲綊 | 鏈～鍐欎笖鏃犳硶浠庨棶棰?琛ㄥご鎺ㄦ柇鐨勫彉閲忎粛浼氳璐ㄩ噺闂ㄧ闃绘柇 |
| 鐪熷疄鏁版嵁闆嗕笂鐨勫鐜版垚鍔熺巼銆佽妭鐪佹椂闂淬€佸鎴蜂粯璐规剰鎰?| 鏆傛棤鎺堟潈璇曠偣璁板綍 | 闇€瑕佽瘯鐐规柟妗堛€佹棩蹇楀拰鐮旂┒鑰呭鏍?| 寰呰ˉ璇佹嵁 | 涓嶅緱鍐欐垚鍑嗙‘鐜囥€佹晥鐜囨彁鍗囨垨鏀跺叆 |
| 甯傚満瑙勬ā銆佺珵鍝佷唤棰濄€佷环鏍煎尯闂淬€佹斂绛栨晥鏋?| 鏆傛棤澶栭儴鏍搁獙璧勬枡 | 闇€瑕佸彲閾炬帴鐨勬潈濞佹潵婧愭垨閲囪喘璁胯皥 | 寰呰ˉ璇佹嵁 | 涓嶅緱缂栭€犵簿纭暟瀛?|

## 椋庨櫓闂ㄧ

| 椋庨櫓 | 鍙戠幇淇″彿 | 褰撳墠澶勭悊 | 鏀捐鏉′欢 |
| --- | --- | --- | --- |
| 鎶婄浉鍏宠鎴愬洜鏋?| 瑙傚療鍥炲綊鎴栨棤鍒嗛厤鏈哄埗 | 璁″垝杈圭晫鍥哄畾涓?conditional association | 鏈夎璁°€佽瘑鍒亣璁惧拰鐮旂┒鑰呯‘璁?|
| 鏁版嵁涓庤鏂囪瘉鎹敊閰?| evidence role 涓嶆槸 user_dataset | 璁烘枃鍙繘鍏?method_reference | 鏁版嵁闆嗕笌鍗忚鐙珛鐧昏 |
| 缂哄け澶勭悊鏀瑰彉浼拌鐩爣 | 璁″垝娌℃湁 missingness strategy | 鎵ц鍓嶉樆鏂?| 鍐荤粨璁″垝涓庡崗璁竴鑷?|
| 鏈潵淇℃伅娉勬紡 | 鏃堕棿鎺掑簭鎴栧垏鍒嗕笉鏄?| 鏃堕棿搴忓垪鎵ц鍓嶆鏌?| 鏃堕棿鍒椼€佺獥鍙ｅ拰棰勬祴瑙嗙晫鍙璁?|
| 灏忔牱鏈繃搴﹁В璇?| 鍙姤鍛?p 鍊兼垨鈥滄棤鏄捐憲宸紓鈥?| 杈撳嚭鏁堝簲閲忋€佸尯闂淬€佺疆鎹㈠拰鐣欎竴娉?| 鐮旂┒鑰呭鏍镐笉纭畾鎬?|
| 鍘熷鏁版嵁瓒婃潈鎴栬矾寰勬硠婕?| 璇锋眰鍖呭惈鏈嶅姟鍣ㄧ粷瀵硅矾寰?| API 浠诲姟鍝嶅簲鍓ョ source/output 璺緞锛涘墠绔笉鏀剁粷瀵硅矾寰?| 鍙楁帶鏂囦欢寮曠敤銆佹潈闄愬拰瀹¤鏃ュ織 |
| 鎶婃墽琛屽畬鎴愯鎴愮鐮旂粨璁?| `executed` 琚綋浣滃彂琛ㄧ粨鏋?| 鎵€鏈夌粨鏋滀繚鐣?`human_review_required` | PI/缁熻甯堢瀛楀拰澶嶇幇鏃ュ織 |

## 璇曠偣琛ヨ瘉娓呭崟

1. 鏁版嵁闆嗘巿鏉冦€佺増鏈€乧hecksum銆佹暟鎹瓧鍏稿拰瀹為獙鍗忚銆?2. 浼︾悊/闅愮瀹℃壒銆佽劚鏁忚鍒欍€佽闂鑹插拰鐣欏瓨鏈熼檺銆?3. 鐮旂┒鑰呭鐜版棩蹇楋細杈撳叆鐗堟湰銆佺幆澧冦€佸懡浠ゃ€佷慨鏀硅褰曞拰澶嶆牳缁撹銆?4. 澶嶆潅璁捐琛ュ厖锛氬缁勬瘮杈冦€侀噸澶嶆祴閲忋€丅ootstrap銆佸閲嶆瘮杈冦€乆LSX/Parquet 鍜屽浘褰?Artifact銆?5. 澶栭儴甯傚満銆佺珵鍝併€佹斂绛栧拰鎶ヤ环鏉ユ簮锛涙潵婧愭湭纭鍓嶄繚鐣欌€滃緟琛ヨ瘉鎹€濄€?
