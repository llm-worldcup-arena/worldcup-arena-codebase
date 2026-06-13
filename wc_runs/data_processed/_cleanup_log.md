# data_processed 清洗处置日志(prematch_news / team_news blocked 存根收尾)

> 范围:两仓库全部 status="blocked" 存根(开工扫描共66条)+ 1条场外串稿修复;只动 processed,data_raw 留底不动。
> 上一位已处理3条(其中 AUT 删 `2026-06-13_ap-kdh-ljubicic-callup.json`,原日志见 `team_news/AUT/_cleanup_log.md`:同一AP通稿已有FOX版全文在库)。
> 本次验收(2026-06-13):两仓库541个文章文件,0条 status!="ok",0条 len(original_text)<300;AUT 复扫全ok,无残留采集进程。

**汇总:重抓成功 58 / 换源 8 / 已覆盖删除 1 / 无源删除 0**

| 日期 | 仓库 | 队 | 原文件 | 处置 | 替代文件/备注 |
|---|---|---|---|---|---|
| 2026-06-13 | prematch_news | BEL | 2026-06-10_belgium-squad-yahoo-sports.json | 重抓成功 | 同URL重抓成功,5057字[apify](由先行孤儿进程 refetch_pr_BEL_0610 完成) |
| 2026-06-13 | prematch_news | BEL | 2026-06-10_fifa-warmup-fixtures.json | 重抓成功 | 同URL重抓成功,38924字[apify](由先行孤儿进程 refetch_pr_BEL_0610 完成) |
| 2026-06-13 | prematch_news | BIH | 2026-06-10_fifa-bih-squad.json | 重抓成功 | 同URL重抓成功,2505字[apify] |
| 2026-06-13 | prematch_news | BRA | 2026-06-10_bra-neymar-squad-cbssports.json | 重抓成功 | 同URL重抓成功,40500字[apify] |
| 2026-06-13 | prematch_news | CAN | 2026-06-09_ctv-can-squad.json | 重抓成功 | 同URL重抓成功,1217字[apify] |
| 2026-06-13 | prematch_news | CAN | 2026-06-10_fifa-can-squad.json | 重抓成功 | 同URL重抓成功,3393字[apify] |
| 2026-06-13 | prematch_news | COD | 2026-06-10_drc-squad-fifa.json | 重抓成功 | 同URL重抓成功,2634字[apify] |
| 2026-06-13 | prematch_news | CZE | 2026-06-10_fifa-cze-hlozek.json | 重抓成功 | 同URL重抓成功,2453字[apify] |
| 2026-06-13 | prematch_news | CZE | 2026-06-10_squawka-cze-analysis.json | 重抓成功 | 同URL重抓成功,8977字[apify] |
| 2026-06-13 | prematch_news | EGY | 2026-06-10_egypt-squad-named-fifa.json | 重抓成功 | 同URL重抓成功,2161字[apify] |
| 2026-06-13 | prematch_news | EGY | 2026-06-10_egypt-squad-olympics.json | 重抓成功 | 同URL重抓成功,3108字[apify] |
| 2026-06-13 | prematch_news | EGY | 2026-06-10_neymar-egypt-friendly-espn.json | 重抓成功 | 同URL重抓成功,1054字[apify] |
| 2026-06-13 | prematch_news | ESP | 2026-06-10_espn-wc2026-injuries-tracker.json | 重抓成功 | 同URL重抓成功,21875字[apify] |
| 2026-06-13 | prematch_news | ESP | 2026-06-10_spain-squad-announcement-wc2026-fifa.json | 重抓成功 | 同URL重抓成功,4001字[apify] |
| 2026-06-13 | prematch_news | HAI | 2026-06-10_hai-all-48-squads-espn.json | 重抓成功 | 同URL重抓成功,59427字[apify] |
| 2026-06-13 | prematch_news | HAI | 2026-06-10_hai-squad-announcement-fifa.json | 重抓成功 | 同URL重抓成功,3854字[apify] |
| 2026-06-13 | prematch_news | HAI | 2026-06-10_hai-visa-player-espn.json | 换源 | ESPN URL经Apify串稿("13 stats"正文) → 2026-06-10_hai-visa-player-espn-sub.json(同一AP通稿,Washington Times,1349字) |
| 2026-06-13 | prematch_news | HAI | 2026-06-10_hai-warmup-results-fifa.json | 重抓成功 | 同URL重抓成功,38924字[apify] |
| 2026-06-13 | prematch_news | HAI | 2026-06-10_wc2026-injuries-tracker-espn.json | 重抓成功 | 同URL重抓成功,38057字[apify] |
| 2026-06-13 | prematch_news | IRN | 2026-06-10_iran-squad-fifa-preliminary.json | 重抓成功 | 同URL重抓成功,1813字[apify] |
| 2026-06-13 | prematch_news | JOR | 2026-06-10_jordan-squad-fifa-official.json | 重抓成功 | 同URL重抓成功,2141字[apify] |
| 2026-06-13 | prematch_news | JOR | 2026-06-10_jordan-squad-olympics.json | 重抓成功 | 同URL重抓成功,777字[apify] |
| 2026-06-13 | prematch_news | KSA | 2026-06-10_saudi-wc26-squad-alarabiya.json | 重抓成功 | 同URL重抓成功,7154字[apify] |
| 2026-06-13 | prematch_news | NOR | 2026-06-10_norway-world-cup-squad-analysis-squawka.json | 重抓成功 | 同URL重抓成功,6120字[apify] |
| 2026-06-13 | prematch_news | POR | 2026-06-10_por-ronaldo-miss-friendlies-espn.json | 重抓成功 | 同URL重抓成功,3426字[apify] |
| 2026-06-13 | prematch_news | QAT | 2026-06-10_qat-el-salvador-friendly.json | 换源 | ESPN比分页无正文 → 2026-06-10_qat-warmup-results-fifa-sub.json(FIFA官方warm-up汇总,含"Qatar 0-0 El Salvador"全段,39039字) |
| 2026-06-13 | prematch_news | QAT | 2026-06-10_qat-ireland-friendly.json | 换源 | 同上 → 2026-06-10_qat-warmup-results-fifa-sub.json(含"Republic of Ireland 1-0 Qatar"全段) |
| 2026-06-13 | prematch_news | SCO | 2026-06-10_sco-warmup-results-fifa.json | 重抓成功 | 同URL重抓成功,38924字[apify] |
| 2026-06-13 | prematch_news | SEN | 2026-06-10_senegal-wc2026-squad-espn.json | 已覆盖删除 | 同仓库已有 ok 全文同主题:2026-06-10_senegal-wc2026-squad-fifa.json + ..._senegal-wc2026-squad-bein.json(ESPN名单页本身无正文) |
| 2026-06-13 | prematch_news | SEN | 2026-06-10_senegal-wc2026-squad-fifa.json | 重抓成功 | 同URL重抓成功,1879字[apify] |
| 2026-06-13 | prematch_news | SWE | 2026-06-10_swe-squad-freemalaysia.json | 重抓成功 | 同URL重抓成功,5680字[apify] |
| 2026-06-13 | prematch_news | TUR | 2026-06-10_tur-squad-olympics.json | 重抓成功 | 同URL重抓成功,1105字[apify] |
| 2026-06-13 | prematch_news | URU | 2026-06-10_uruguay-araujo-injury-world-cup-2026.json | 换源 | MSN死链 → 2026-06-08_uruguay-araujo-injury-world-cup-2026-sub.json(Barca Blaugranes原创源,873字);中途Yahoo替代抓成串稿已删 |
| 2026-06-13 | prematch_news | URU | 2026-06-10_uruguay-midfielder-injury-misses-world-cup.json | 重抓成功 | 同URL重抓成功,1058字[apify] |
| 2026-06-13 | prematch_news | URU | 2026-06-10_uruguay-squad-world-cup-2026-olympics.json | 重抓成功 | 同URL重抓成功,1459字[apify] |
| 2026-06-13 | prematch_news | USA | 2026-06-10_chris-richards-injury-time.json | 重抓成功 | 同URL重抓成功,5774字[apify] |
| 2026-06-13 | prematch_news | USA | 2026-06-10_chris-richards-ready-espn.json | 重抓成功 | 同URL重抓成功,3044字[apify] |
| 2026-06-13 | prematch_news | USA | 2026-06-10_chris-richards-ready-nbcla.json | 重抓成功 | 同URL重抓成功,1903字[apify] |
| 2026-06-13 | prematch_news | USA | 2026-06-10_usa-squad-announcement-fifa.json | 重抓成功 | 同URL重抓成功,3156字[apify] |
| 2026-06-13 | prematch_news | USA | 2026-06-10_usmnt-injured-defender-yahoo.json | 重抓成功 | 同URL重抓成功,2664字[apify] |
| 2026-06-13 | team_news | ALG | 2026-06-13_athlon-bensebaini-miss-opener.json | 重抓成功 | 同URL重抓成功,3714字[apify] |
| 2026-06-13 | team_news | BIH | 2026-06-13_ap_dzeko_fit_fight.json | 换源 | AP原链429;并行代理换AOL刊发同稿覆盖同名文件(3538字,正文已核对为Džeko fit fight本稿) |
| 2026-06-13 | team_news | CRO | 2026-06-13_fifa-croatia-squad-named.json | 重抓成功 | 同URL重抓成功,2516字[apify] |
| 2026-06-13 | team_news | CRO | 2026-06-13_yahoo-croatia-wc2026-squad.json | 重抓成功 | 同URL重抓成功,5560字[apify] |
| 2026-06-13 | team_news | CZE | 2026-06-13_squawka-czech-squad-analysis.json | 重抓成功 | 同URL重抓成功,8977字[apify] |
| 2026-06-13 | team_news | ECU | 2026-06-13_fifa-ecuador-squad-announcement.json | 重抓成功 | 同URL重抓成功,2354字[apify] |
| 2026-06-13 | team_news | ECU | 2026-06-13_squawka-civ-ecu-team-news.json | 重抓成功 | 同URL重抓成功,5090字[apify] |
| 2026-06-13 | team_news | GER | 2026-06-13_ap-germany-tuneup-without-karl.json | 换源 | Daily Gazette 429 → 2026-06-13_ap-germany-tuneup-without-karl-sub.json(同一AP通稿,FOX Sports刊发,1821字) |
| 2026-06-13 | team_news | GHA | 2026-06-13_ghanasoccernet-injuries-squad-balance.json | 重抓成功 | 同URL重抓成功,7405字[apify];曾被并行代理覆盖回blocked,三次重试后稳定ok |
| 2026-06-13 | team_news | KOR | 2026-06-13_koreaherald-choyumin-out.json | 重抓成功 | 同URL重抓成功,2284字[apify] |
| 2026-06-13 | team_news | KOR | 2026-06-13_koreatimes-choyumin-out.json | 重抓成功 | 同URL重抓成功,2757字[apify] |
| 2026-06-13 | team_news | KOR | 2026-06-13_sedaily-baejunho-sidelined.json | 重抓成功 | 同URL重抓成功,3891字[apify] |
| 2026-06-13 | team_news | KSA | 2026-06-13_fifa-donis-squad.json | 重抓成功 | 同URL重抓成功,2773字[apify] |
| 2026-06-13 | team_news | KSA | 2026-06-13_olympics-ksa-squad.json | 重抓成功 | 同URL重抓成功,1008字[apify] |
| 2026-06-13 | team_news | MEX | 2026-06-13_espn-injury-tracker.json | 重抓成功 | 同URL重抓成功,37903字[apify] |
| 2026-06-13 | team_news | MEX | 2026-06-13_tribunademexico-lesionados.json | 重抓成功 | 同URL重抓成功,3287字[apify] |
| 2026-06-13 | team_news | NED | 2026-06-13_espn-verbruggen-doubt.json | 换源 | ESPN URL经Apify串稿 → 2026-06-11_espn-verbruggen-doubt-sub.json(同一AP通稿,KCTV5,2572字) |
| 2026-06-13 | team_news | NOR | 2026-06-13_fifa-nor-squad.json | 重抓成功 | 同URL重抓成功,2174字[apify] |
| 2026-06-13 | team_news | NOR | 2026-06-13_olympics-nor-squad.json | 重抓成功 | 同URL重抓成功,1096字[apify] |
| 2026-06-13 | team_news | NZL | 2026-06-13_squawka-nzl-analysis.json | 重抓成功 | 同URL重抓成功,7903字[apify] |
| 2026-06-13 | team_news | PAN | 2026-06-13_fifa-pan-squad.json | 重抓成功 | 同URL重抓成功,2418字[apify] |
| 2026-06-13 | team_news | PAR | 2026-06-13_riotimes-enciso.json | 重抓成功 | 同URL重抓成功,5906字[apify] |
| 2026-06-13 | team_news | PAR | 2026-06-13_yahoo-enciso-injured.json | 重抓成功 | 同URL重抓成功,2557字[apify] |
| 2026-06-13 | team_news | RSA | 2026-06-13_espn_broos_zwane_red.json | 重抓成功 | 同URL重抓成功,15849字[apify] |
| 2026-06-13 | team_news | RSA | 2026-06-13_thesouthafrican_fines.json | 重抓成功 | 同URL重抓成功,3905字[apify] |
| 2026-06-13 | team_news | TUN | 2026-06-13_fifa_tun_squad_named.json | 重抓成功 | 同URL重抓成功,3956字[apify] |
| 2026-06-13 | prematch_news | ARG | 2026-06-10_arg-balerdi-calf-injury-out.json | 换源 | 不在原blocked清单(并行代理0748重抓产物,status=ok但正文为"13 stats"串稿);同URL重试仍串稿 → 删原件,换 2026-06-10_arg-balerdi-calf-injury-out-sub.json(beIN SPORTS,1880字) |

---

# 第二轮:串稿清洗(status=ok 但正文为别的页面;2026-06-13)

> 范围:两仓库 status=ok 的「串稿」——Apify 抓 Yahoo/aawsat/ESPN 被跳转到聚合页(全48队名单/1-48排名/赛程/十大焦点战/live updates/Meet the USMNT/他队赛报)。
> 判定标准:正文是否覆盖该队该主题(title 元数据被串但**正文含目标文章全文**的 hub/快照件 → 核验通过保留)。
> 终扫:两仓库全部 ok 文件 title 双层扫描(聚合页模式串 + 他队国名启发式),复扫 0 残留;收尾 540 文章文件全 ok、0 blocked、0 短文。
> 交叉影响:被删/换文件涉及的各队 summary ⑦「多源核实」事实均仍有 ≥1 独立在库 ok 源(COD名单×4源/ARG Dibu ANI+Goal/URU AUF声明+RotoWire/IRQ ANI+A-Leagues/GER Bundesliga官网+Sports Mole/KSA VAVEL/SCO Goal+Scotsman+ScottishFA);CHANGELOG/summary 无直接文件名引用 → **失source事实 0,无需改 summary**。

**汇总:重抓成功 3 / 换源 11 / 已覆盖删除 1 / 无源删除 0 / 核验通过保留 9**

| 日期 | 仓库 | 队 | 原文件 | 处置 | 替代文件/备注 |
|---|---|---|---|---|---|
| 2026-06-13 | team_news | BEL | 2026-06-13_yahoo_kdb_ready.json | 重抓成功 | 原存全48队名单页;同URL重抓2608字[apify],正文核对为KDB"那不勒斯伤难解释/已为世界杯准备好"本稿 |
| 2026-06-13 | team_news | COD | 2026-06-13_yahoo_cod_squad.json | 已覆盖删除 | 原存1-48排名页,重抓仍串;该Yahoo稿系The Football Faithful联发,原创源已在库(prematch 2026-06-06_drc-squad-footballfaithful.json)+FIFA官方/heavy/soccergraph共4个ok名单源 |
| 2026-06-13 | team_news | ARG | 2026-06-13_yahoo_dibu_cleared.json | 换源 | 原存墨西哥2-0南非赛报,重抓仍串 → 2026-06-13_yahoo_dibu_cleared-sub.json(同故事UPI通讯社版,2157字,正文核对为Dibu完成合练解锁首战) |
| 2026-06-13 | team_news | URU | 2026-06-13_yahoo_araujo_brother_bielsa.json | 换源 | 原存墨西哥赛报,重抓仍串 → 2026-06-09_yahoo_araujo_brother_bielsa-sub.json(Barca Blaugranes原创源,922字,正文核对为其兄"感谢你赛前弄伤球员"炮轰Bielsa本稿) |
| 2026-06-13 | team_news | URU | 2026-06-13_yahoo_araujo_injury_statement.json | 重抓成功 | 原存十大焦点战页;同URL重抓1244字[apify],正文核对为Araujo伤情+AUF官方声明本稿 |
| 2026-06-13 | team_news | POR | 2026-06-13_yahoo_por_squad.json | 换源 | 原存十大焦点战页,重抓仍串 → 2026-06-06_yahoo_por_squad-sub.json(The Football Faithful原创源同稿,3025字) |
| 2026-06-13 | team_news | IRQ | 2026-06-13_aawsat-iraq-conclude-prep-venezuela.json | 换源 | 原存姆巴佩/登贝莱稿(aawsat聚合页),重抓仍串 → 2026-06-10_aawsat-iraq-conclude-prep-venezuela-sub.json(同一路透通稿The Star刊发,1055字,0-2负委内瑞拉+优素福红牌全文) |
| 2026-06-13 | team_news | IRN | 2026-06-13_yahoo-taremi-tense-atmosphere-visa.json | 换源 | 原存赛程页,重抓变特朗普稿 → 2026-06-13_yahoo-taremi-tense-atmosphere-visa-sub.json(ClutchPoints原创源,2264字,Taremi抨击美签证/紧张氛围本稿) |
| 2026-06-13 | team_news | GER | 2026-06-13_yahoo-neuer-returns-training-curacao.json | 换源 | 原存全48队名单页,重抓仍串 → 2026-06-13_yahoo-neuer-returns-training-curacao-sub.json(Bulinews原创源同标题稿,1133字) |
| 2026-06-13 | team_news | GER | 2026-06-13_yahoo-nagelsmann-confirms-neuer-start.json | 换源 | 待核验组→坐实串稿(存全48队名单页/Day1标题,重抓变USMNT赛报) → 2026-06-13_yahoo-nagelsmann-confirms-neuer-start-sub.json(Bulinews原创源同slug稿,1529字) |
| 2026-06-13 | prematch_news | URU | 2026-06-10_uruguay-squad-world-cup-2026-olympics.json | 换源 | 待核验组→坐实串稿(olympics.com乌拉圭名单URL存"已晋级球队列表",全文0次提及Uruguay;首轮被误记"重抓成功"),重抓仍同页 → 2026-05-31_uruguay-squad-world-cup-2026-olympics-sub.json(SI乌拉圭26人名单全文,3208字) |
| 2026-06-13 | prematch_news | MEX | 2026-06-10_yahoo-mex-squad-when.json | 核验通过(保留) | 正文确为"墨名单何时公布"Athlon Sports原稿(Aguirre/FMF/5-31官宣),仅title元数据被Yahoo串改为Day1看点 |
| 2026-06-13 | prematch_news | PAN | 2026-06-10_pan-squad-yahoo.json | 核验通过(保留) | 全48队名单页快照内确含巴拿马26人完整名单段(含主帅Christiansen),按规则保留 |
| 2026-06-13 | prematch_news | MEX | 2026-06-10_yahoo-mex-squad-named.json | 核验通过(保留) | 终扫捕获;正文确为墨西哥官宣26人名单全文(完整名单+落选分析),仅title被串改为墨南赛报标题 |
| 2026-06-13 | team_news | KSA | 2026-06-13_aawsat-ksa-senegal-scoreless-final-friendly.json | 换源 | 终扫捕获(aawsat聚合页:正文仅首行正确,余为F1/Dembele稿),重抓仍串 → 2026-06-10_aawsat-ksa-senegal-scoreless-final-friendly-sub.json(同通稿Arab News刊发,1408字,0-0塞内加尔全文) |
| 2026-06-13 | team_news | SUI | 2026-06-13_yahoo-embolo-esta-denied.json | 核验通过(保留) | 终扫捕获;正文确为Embolo ESTA被卡未随队赴美Athlon原稿全文(Embolo×7/ESTA×3),仅title被串改为特朗普标题 |
| 2026-06-13 | prematch_news | COL | 2026-06-10_col-james-diaz-squad-espn.json | 核验通过(保留) | 终扫捕获;ESPN hub快照title伪("Meet the USMNT"),但J罗/Díaz领衔哥伦比亚名单目标文章全文在内(Lizzy Becherano 5-25稿+完整名单) |
| 2026-06-13 | prematch_news | COL | 2026-06-10_col-james-hospitalized-espn.json | 核验通过(保留) | 同上;J罗脱水住院稿全文在内 |
| 2026-06-13 | prematch_news | CRO | 2026-06-10_cro-modric-5th-wc-espn.json | 核验通过(保留) | 同上;莫德里奇第5届世界杯入选稿全文+克罗地亚名单在内 |
| 2026-06-13 | team_news | ESP | 2026-06-13_espn-yamal-nico-skip-last-warmup.json | 核验通过(保留) | 同上;Yamal/Nico Williams缺席末轮热身稿全文在内(Alex Kirkland 6-7稿) |
| 2026-06-13 | team_news | GHA | 2026-06-13_espn-partey-denied-entry-canada.json | 核验通过(保留) | 终扫捕获;title伪(Larin/加拿大赛报)但Partey加拿大拒签稿全文完整在内(Tom Hamilton 6-12稿,快照尾部混入CAN-BIH赛报) |
| 2026-06-13 | team_news | ARG | 2026-06-13_espn_dibu_gloves.json | 换源 | 终扫捕获(纯"Meet the USMNT"文,Martinez/Argentina 0提及),重抓变live updates页 → 2026-06-13_espn_dibu_gloves-sub.json(espn.co.uk镜像同id同稿,2145字,Dibu戴双手套完成合练全文) |
| 2026-06-13 | team_news | FRA | 2026-06-13_espn-deschamps-eases-saliba-fears.json | 重抓成功 | 终扫捕获(纯USMNT文);同URL重抓3580字[apify],Deschamps安抚Saliba背伤稿全文在内 |
| 2026-06-13 | prematch_news | SCO | 2026-06-10_sco-gilmour-injury-espn.json | 换源 | 终扫捕获(纯USMNT文,Gilmour 0提及);同URL与espn.co.uk镜像均跳live页、Hexham(PA)403 → 2026-06-10_sco-gilmour-injury-espn-sub.json(FOX Sports同故事,3585字,Gilmour伤退无缘世界杯全文) |
| 2026-06-13 | team_news | SUI | 2026-06-13_switzerland-team-news-fifa-official.json | 已覆盖删除 | 1138轮FIFA聚合页0字被挡,SUI另有多篇ok源覆盖 |
