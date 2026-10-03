/* theories.js — the scenario playbook engine ("does the play on one stock apply
 * to another?"). Every listed stock is classified into an ARCHETYPE (public
 * facts only); every SCENARIO (crash, earnings miss, rate shock...) states, per
 * archetype, what the market has historically done to shares like it, the
 * mechanism, a precedent, and what to watch. Bands are historical base rates,
 * approximate, for education — not predictions, not financial advice.
 * No portfolio data lives here: holdings stay in the visitor's browser. */
(function () {
  window.Q = window.Q || {};

  var ARCH = {
    'fortress-mega': { label: 'Fortress mega-cap', desc: 'Net cash / self-funding, dominant franchise' },
    'quality-large': { label: 'Quality large-cap', desc: 'Profitable, moderate debt, real moat' },
    'leveraged-cyclical': { label: 'Leveraged cyclical (fleet/rental)', desc: 'Debt-financed assets, demand tied to the cycle — the Hertz profile' },
    'smallcap-industrial': { label: 'Small-cap industrial/services', desc: 'Profitable niche operator, thin trading liquidity' },
    'semis-growth': { label: 'Semiconductor / AI-linked', desc: 'High multiple, revenue correlated to the tech capex cycle' },
    'pre-profit-burner': { label: 'Pre-profit cash burner', desc: 'Negative FCF; lives on the financing window' },
    'micro-spec': { label: 'Speculative micro-cap', desc: 'Story stock; financing- and dilution-driven' },
    'commodity-producer': { label: 'Commodity producer', desc: 'Price-taker with operating leverage to the commodity' },
    'precious-metal': { label: 'Precious-metals exposure', desc: 'Gold/silver miners and metal ETFs' },
    'regulated-utility': { label: 'Regulated utility', desc: 'Stable demand, rate-sensitive, heavy debt by design' },
    'medtech': { label: 'Medical devices', desc: 'Defensive demand, procedure-volume driven' },
    'turnaround': { label: 'Turnaround / legacy tech', desc: 'Declining core, optionality bet on reinvention' },
    'crypto-proxy': { label: 'Crypto proxy / miner', desc: 'Equity wrapper on crypto prices and hashprice' }
  };

  // Public classification facts for common tickers (base symbol, exchange suffix stripped).
  var MAP = {
    AAPL: 'fortress-mega', GOOG: 'fortress-mega', GOOGL: 'fortress-mega', MSFT: 'fortress-mega', AMZN: 'fortress-mega', META: 'fortress-mega', NVDA: 'fortress-mega',
    CARR: 'quality-large', BSX: 'quality-large', MDT: 'medtech', NPCE: 'pre-profit-burner',
    HTZ: 'leveraged-cyclical', WSC: 'leveraged-cyclical', CAR: 'leveraged-cyclical', URI: 'leveraged-cyclical', R: 'leveraged-cyclical',
    TRNS: 'smallcap-industrial', FLXS: 'smallcap-industrial', FC: 'smallcap-industrial',
    LSCC: 'semis-growth', STM: 'semis-growth', STHH: 'semis-growth', INTC: 'turnaround', AMD: 'semis-growth', MU: 'semis-growth', AVGO: 'semis-growth', SUPX: 'micro-spec',
    EOSE: 'pre-profit-burner', FLNC: 'pre-profit-burner', OPTT: 'micro-spec', PRSO: 'micro-spec', HOLO: 'micro-spec', QUTX: 'micro-spec', NAMM: 'micro-spec', LEAP: 'micro-spec', GPRO: 'turnaround',
    APA: 'commodity-producer', CVE: 'commodity-producer', WCP: 'commodity-producer', XOM: 'commodity-producer', HBM: 'commodity-producer', CS: 'commodity-producer',
    IMG: 'precious-metal', SLV: 'precious-metal', GLD: 'precious-metal', AEM: 'precious-metal',
    EIX: 'regulated-utility', BB: 'turnaround', BTDR: 'crypto-proxy', MARA: 'crypto-proxy', RIOT: 'crypto-proxy',
    LLY: 'quality-large', PFE: 'quality-large', JPM: 'quality-large', TSLA: 'quality-large'
  };

  // Scenario playbooks. Each cell: band (historical, approximate), what happens
  // ("companies like this have..."), a precedent, and what to watch.
  var SCENARIOS = [
    { id: 'crash', name: 'Systemic crash / credit freeze', theory: 'The Hertz Lesson: crashes reprice everyone; leverage decides who survives',
      cells: {
        'fortress-mega': { band: '−30% to −55%', play: 'Fall hard on repricing but keep funding themselves; historically recover and buy distressed rivals at the bottom.', prec: 'Microsoft ≈−44%, Apple ≈−57% in 2008 — both at new highs within ~2 years (approx.)', watch: 'Nothing existential — watch for the buying opportunity, not the obituary.' },
        'quality-large': { band: '−35% to −55%', play: 'Multiple compresses with the market; dividends and buybacks slow; franchise survives.', prec: 'Large-cap medtech and industrials in 2008–09', watch: 'Net debt / EBITDA creeping over ~3×; refinancing dates.' },
        'leveraged-cyclical': { band: '−60% to −90%, solvency risk', play: 'The full Hertz sequence: demand falls, fleet collateral values fall, and the refinancing window closes — all at once. Equity becomes a thin sliver on a big debt stack.', prec: 'Hertz −85% in 2008–09, Chapter 11 in 2020; Avis ≈−90% in 2008; United Rentals ≈−80%', watch: 'Debt due inside 24 months, revolver draw-downs, used-asset resale prices, rental utilization.' },
        'smallcap-industrial': { band: '−40% to −65%', play: 'Liquidity vanishes first — sellers hit wide bids; fundamentals hold up better than the tape. Historically the group overshoots down, then outperforms in recovery.', prec: 'Russell 2000 ≈−60% peak-to-trough 2007–09 vs S&P ≈−57%, with faster rebound', watch: 'Customer concentration; whether the balance sheet lets them buy back stock into the hole.' },
        'semis-growth': { band: '−50% to −75%', play: 'Capex-linked revenue is the first line item customers cut; multiple compression doubles the damage.', prec: 'SOX index ≈−70% in 2000–02 and ≈−60% in 2008–09', watch: 'Inventory builds, order push-outs, hyperscaler capex guidance.' },
        'pre-profit-burner': { band: '−70% to −95%, dilution or death', play: 'The financing window closes exactly when cash runs lowest. Survivors issue equity at crushed prices (massive dilution); the rest restructure.', prec: '2000–02 dot-coms; 2022 SPAC cohort ≈−80–95% median', watch: 'Months of runway vs cash burn; ATM/shelf filings; going-concern language.' },
        'micro-spec': { band: '−80% to −100%', play: 'Bids disappear. Reverse splits, delisting notices, and financings at any price. Many never recover.', prec: 'The long tail of every crash — most sub-$100M story stocks of 2000 and 2008 no longer exist', watch: 'Compliance notices, dilution filings, insider buying (the only bullish tell).' },
        'commodity-producer': { band: '−50% to −75%', play: 'Demand-shock crashes take the commodity down with equities; operating leverage cuts both ways.', prec: 'Oil ≈−$100 peak-to-trough 2008; E&Ps −60–80%', watch: 'Breakeven price vs spot; hedge book; debt covenants.' },
        'precious-metal': { band: '−25% then haven bid', play: 'Forced selling hits everything first — even gold fell ~30% in late 2008 — then the haven bid returns before most assets.', prec: 'Gold −~30% Mar–Nov 2008, new highs by 2009–11', watch: 'Real yields; the turn usually comes when the Fed pivots.' },
        'regulated-utility': { band: '−20% to −40%', play: 'Falls least — demand is captive — but heavy structural debt means rate spikes and credit stress still bite.', prec: 'Utilities ≈−40% 2008–09 vs −57% S&P', watch: 'Regulatory rate-case outcomes; wildfire/storm liabilities where relevant.' },
        'medtech': { band: '−30% to −45%', play: 'Procedures get deferred, not cancelled — revenue dips then catches up. One of the better places to hide inside equities.', prec: 'Large medtech 2008–09 drawdowns ≈ 2/3 of the index’s', watch: 'Hospital capex freezes for equipment names.' },
        'turnaround': { band: '−50% to −80%', play: 'A crash removes the time and the financing a turnaround needs. The story pauses; the cash burn doesn’t.', prec: 'Mid-turnaround names in 2008 (Sprint ≈−70%)', watch: 'Whether the core business funds the pivot without markets.' },
        'crypto-proxy': { band: '−70% to −90%', play: 'Trades as levered beta on crypto, which historically falls 2–3× equities in risk-off. Hashprice compression squeezes miners on both ends.', prec: 'BTC −65% in 2022; miners −90%+', watch: 'Cost-to-mine vs spot; fleet financing terms (GPU/ASIC-backed debt).' }
      } },
    { id: 'miss1', name: 'A single earnings miss', theory: 'The expectations gap: the stock moves on the surprise, the multiple moves on credibility',
      cells: {
        'fortress-mega': { band: '−3% to −10% next day', play: 'One miss is forgiven if the franchise metrics hold; the stock typically round-trips within a quarter.', prec: 'Mega-cap post-miss drift is historically mild', watch: 'Whether guidance moved — the guide matters more than the quarter.' },
        'quality-large': { band: '−5% to −12%', play: 'A gap down, then a drift that follows the guidance revision.', prec: 'Post-earnings-announcement drift literature: the first move usually continues for ~60 days', watch: 'Estimate revisions in the following two weeks.' },
        'leveraged-cyclical': { band: '−10% to −25%', play: 'A miss here reads as a cycle signal, not a stumble — the market marks down the whole forward curve and re-checks the debt math.', prec: 'Hertz shares dropped hard on its Feb 2008 guidance miss well before the crash', watch: 'Utilization and pricing disclosures inside the release.' },
        'smallcap-industrial': { band: '−10% to −20%', play: 'Thin coverage means one miss can orphan the stock for quarters.', prec: 'Small-cap post-miss drift runs longer than large-cap', watch: 'Whether management buys the dip personally.' },
        'semis-growth': { band: '−12% to −25%', play: 'High multiples price perfection; a miss breaks the narrative premium first, numbers second.', prec: 'High-multiple semis routinely gap −15%+ on first misses', watch: 'Book-to-bill and backlog language.' },
        'pre-profit-burner': { band: '−15% to −35%', play: 'A miss shortens the runway story — it’s a financing event, not an earnings event.', prec: 'Pre-profit growth cohort 2021–22', watch: 'Cash line vs last quarter; any hint of a raise.' },
        'micro-spec': { band: '−20% to −50%', play: 'One bad print can be terminal for the narrative that was doing all the lifting.', prec: 'Micro-cap post-miss recoveries are the exception, not the rule', watch: 'Volume on the down move — no volume, no floor.' },
        'commodity-producer': { band: '−5% to −15%', play: 'Cost misses hurt more than revenue misses — the market forgives the commodity price, not sloppy operations.', prec: 'Cost-guidance misses in miners routinely −10%+', watch: 'Per-unit cost guidance (AISC, opex/boe).' },
        'precious-metal': { band: '−5% to −15%', play: 'Production/cost misses hit miners; the metal itself shrugs.', prec: 'Gold miners’ chronic 2011–15 cost misses', watch: 'Grade and recovery trends.' },
        'regulated-utility': { band: '−2% to −8%', play: 'Regulated returns make misses small and mean-reverting.', prec: 'Utility misses rarely re-rate the stock', watch: 'Rate-case timing.' },
        'medtech': { band: '−5% to −15%', play: 'Procedure-volume misses get bought; pipeline/regulatory misses do not.', prec: 'Device-recall misses are the exception — those re-rate', watch: 'Which kind of miss it was.' },
        'turnaround': { band: '−10% to −30%', play: 'Every quarter is a referendum on the thesis; a miss resets the clock and the patience.', prec: 'Serial-restructurer post-miss drift is strongly negative', watch: 'Whether the turnaround KPI (not EPS) moved.' },
        'crypto-proxy': { band: '−10% to −25%', play: 'Earnings are noise next to the coin price — unless the miss reveals cost or custody problems.', prec: 'Miner misses on energy costs 2022', watch: 'Cost per coin mined.' }
      } },
    { id: 'miss3', name: 'Three straight misses', theory: 'The credibility break: after the third miss the market stops pricing the guidance and starts pricing the management',
      cells: {
        'fortress-mega': { band: '−25% to −40% cumulative + multiple de-rate', play: 'Even franchises lose the benefit of the doubt: the multiple de-rates a full tier and activist/succession pressure starts. Recovery historically needs a management or strategy change, not just a beat.', prec: 'Intel 2021–24: serial disappointments → multiple de-rated from ~14× to single digits, CEO change followed', watch: 'Board language, buyback pace, whether the CFO survives.' },
        'quality-large': { band: '−30% to −50% cumulative', play: 'Companies like this get re-classified from “compounder” to “show-me” — analysts move estimates below guidance and keep them there. The drift after a third consecutive miss is the most persistent in the drift literature.', prec: 'Boston Scientific’s mid-2010s guide-down cycle: years in the penalty box before the re-rate', watch: 'Guidance methodology changes — the honest tell that management is resetting the bar to beatable.' },
        'leveraged-cyclical': { band: '−50% to −75% cumulative, credit watch', play: 'Three misses in a leveraged cyclical reads as “the cycle has turned” — credit spreads widen, and the equity starts trading as an option on refinancing.', prec: 'Hertz 2018–19: repeated misses → equity treated as a leveraged stub well before COVID finished it', watch: 'Bond prices, not the stock — credit sees it first.' },
        'smallcap-industrial': { band: '−40% to −60% cumulative', play: 'Coverage drops, the multiple halves, and the stock goes dormant until an acquirer or activist shows up. Historically these resolve by takeout more often than by organic recovery.', prec: 'Serial-missing small industrials are a classic PE-takeout pool', watch: '13D filings; insider accumulation.' },
        'semis-growth': { band: '−50% to −70% cumulative', play: 'Three misses = the cycle thesis is dead; the stock re-prices from a growth multiple to a cyclical one — two compressions stacked.', prec: 'Post-2000 semis that missed thrice traded at single-digit P/Es within 18 months', watch: 'Whether the miss is share loss (terminal) or cycle (recoverable).' },
        'pre-profit-burner': { band: '−60% to −90%, financing spiral risk', play: 'The equity story dies and the financing math takes over: each raise at a lower price dilutes more, which lowers the price — the doom loop. Based on this theory, survival odds track cash runway, not product quality.', prec: 'The 2021 SPAC cohort’s serial missers: median ≈−90% with repeated dilutive raises', watch: 'Runway in quarters; whether a strategic investor steps in (the only clean exit).' },
        'micro-spec': { band: '−70% to −95%', play: 'Three misses in a story stock usually ends the story: reverse split, shelf offering, board churn, and a new narrative pivot (often to whatever is trending).', prec: 'The pivot-to-AI/pivot-to-crypto graveyard', watch: 'Nothing fundamental — only the dilution mechanics.' },
        'commodity-producer': { band: '−30% to −55% cumulative', play: 'Three operational misses mean the asset is worse than the deck said — the market cuts reserves/NAV estimates, not just earnings.', prec: 'Miners that serially miss cost guidance trade at persistent NAV discounts', watch: 'Reserve revisions in the annual report.' },
        'precious-metal': { band: '−30% to −50%', play: 'Chronic missers in miners get valued on “show me the ounces” cash flow only.', prec: 'IAMGOLD’s long guide-down history and persistent discount', watch: 'New management with a credible mine plan — the classic turn signal.' },
        'regulated-utility': { band: '−15% to −30%', play: 'Rare — three misses in a utility implies structural problems (liabilities, regulatory breakdown), and the dividend comes into question.', prec: 'Utility serial-missers are usually liability stories (wildfire, storm)', watch: 'Dividend coverage and liability accruals.' },
        'medtech': { band: '−35% to −55%', play: 'Three misses reads as competitive share loss or reimbursement pressure — both structural. The multiple compresses to value-med-tech and stays there.', prec: 'Mid-cap device serial missers of the 2010s', watch: 'Procedure-share data vs competitors.' },
        'turnaround': { band: '−50% to −80%', play: 'The turnaround premium evaporates entirely; the stock trades to liquidation/sum-of-parts math, and the activist clock starts.', prec: 'BlackBerry’s long post-2013 drift between strategy resets', watch: 'Asset sales — the market pays for cash returned, not promises.' },
        'crypto-proxy': { band: '−50% to −80%', play: 'Serial misses expose the operating leverage as cost problems, and the equity decouples *below* the coin.', prec: 'High-cost miners underperforming BTC itself 2022–23', watch: 'Whether they’re selling treasury coins to fund opex.' }
      } },
    { id: 'rates', name: 'Rate shock (+200 bps)', theory: 'Duration and refinancing: the discount rate hits long-dated stories, the coupon hits leveraged balance sheets',
      cells: {
        'fortress-mega': { band: '−10% to −20%', play: 'Multiple compresses with duration, but net cash means higher rates actually add interest income.', prec: '2022: mega-caps −25–35% on multiple compression alone', watch: 'Nothing balance-sheet — just the multiple.' },
        'quality-large': { band: '−10% to −25%', play: 'Modest de-rate; debt refinances at higher coupons gradually.', prec: '2022 playbook', watch: 'Average debt maturity — longer is safer here.' },
        'leveraged-cyclical': { band: '−25% to −45%', play: 'Every point of rate is a direct EPS cut on floating debt, and the next refinancing reprices the whole stack.', prec: '2022–23: leveraged rentals/REIT-adjacent names −40%+', watch: 'Fixed vs floating mix; next maturity’s coupon delta.' },
        'smallcap-industrial': { band: '−15% to −30%', play: 'Regional-bank credit (their lender base) tightens; growth capex gets shelved.', prec: '2023 small-cap underperformance through the rate peak', watch: 'Revolver terms at renewal.' },
        'semis-growth': { band: '−20% to −40%', play: 'Long-duration cash flows take the discount-rate hit hardest.', prec: '2022: unprofitable tech −60%+, profitable semis −35%', watch: 'The 10-year yield is the stock chart, inverted.' },
        'pre-profit-burner': { band: '−40% to −70%', play: 'The cost of the money they must raise goes up while the value of far-future cash flows goes down — both jaws close.', prec: '2022: the entire pre-profit cohort', watch: 'Any convertible terms — conversion-price resets are the red flag.' },
        'micro-spec': { band: '−40% to −70%', play: 'Risk appetite is the product; rates are its off switch.', prec: '2022 micro-cap drawdowns', watch: 'Same as crash: dilution mechanics.' },
        'commodity-producer': { band: '−5% to −20%, sometimes up', play: 'If rates rise on inflation, commodities often rise too — this cohort historically hedges a rate shock.', prec: '2021–22: energy was the only green sector', watch: 'Why rates are rising — inflation (good for them) vs real-rate spike (bad).' },
        'precious-metal': { band: '−15% to −30%', play: 'Real yields up = gold’s opportunity cost up. The classic headwind.', prec: '2013 taper tantrum: gold −28%, miners −50%', watch: '10-year TIPS yield.' },
        'regulated-utility': { band: '−20% to −35%', play: 'Bond proxies de-rate with bonds, and utilities carry the most structural debt in the market.', prec: '2022–23 utility drawdowns as the 10-year crossed 4%', watch: 'Allowed-ROE vs new debt cost spread.' },
        'medtech': { band: '−10% to −20%', play: 'Moderate duration hit; demand unaffected.', prec: '2022', watch: 'Hospital capex budgets for equipment names.' },
        'turnaround': { band: '−20% to −40%', play: 'Turnarounds are long-duration options; rates crush option value and financing flexibility together.', prec: '2022 killed most concept-stage pivots', watch: 'Interest expense vs operating income trend.' },
        'crypto-proxy': { band: '−30% to −60%', play: 'Crypto trades as the longest-duration risk asset; miners amplify it.', prec: '2022: BTC −65% as rates rose, miners −90%', watch: 'Liquidity conditions (global M2) more than the Fed alone.' }
      } },
    { id: 'ai-winter', name: 'AI capex winter', theory: 'Boom-correlated revenue evaporates first: the second-order casualties are suppliers to the boom, not just the stars',
      cells: {
        'fortress-mega': { band: '−25% to −45%', play: 'The hyperscalers ARE the capex — cutting it protects their cash flow while gutting their suppliers. They reprice but self-fund.', prec: 'Post-2000: Microsoft/Cisco survived their own bubble; suppliers didn’t', watch: 'Capex guidance cuts — theirs is the winter.' },
        'semis-growth': { band: '−50% to −80%', play: 'Order books built on AI demand deflate with it; inventory gluts follow. Based on this theory, the damage ranks by % of revenue tied to AI capex.', prec: 'Optical/telecom suppliers post-2000: −80–95%', watch: 'AI revenue concentration; top-customer disclosures.' },
        'pre-profit-burner': { band: '−60% to −90%', play: 'AI-adjacent burners lose the narrative AND the financing window in the same quarter.', prec: 'Dot-com infrastructure burners 2000–02', watch: 'Runway; pivot announcements (the tell that demand died).' },
        'micro-spec': { band: '−70% to −95%', play: 'AI story micro-caps are the purest expression of the theme — and the first to zero when it turns.', prec: 'The “.com suffix” cohort of 2000, the “AI” rename cohort now', watch: 'Nothing — exit liquidity is the only question.' },
        'crypto-proxy': { band: '−40% to −70%', play: 'Miners pivoting to AI hosting lose the pivot premium; GPU-backed debt (the collateral is the boom) gets margin-called.', prec: 'Chanos’s warning on GPU-collateralized neocloud debt', watch: 'GPU resale values — the collateral IS the cycle.' },
        'leveraged-cyclical': { band: '−30% to −50%', play: 'Data-center construction was the marginal demand for space, power gear and equipment rental — it unwinds through their utilization.', prec: 'Equipment rental in the 2008 construction bust (HERC’s collapse)', watch: 'Non-residential construction starts.' },
        'quality-large': { band: '−15% to −30%', play: 'Second-order exposure through industrial demand (cooling, power, construction).', prec: '2001 industrial slowdown', watch: 'Backlog quality — how much is data-center.' },
        'smallcap-industrial': { band: '−15% to −35%', play: 'Hit only where the order book leaned into data-center work.', prec: '—', watch: 'End-market disclosure in the 10-K.' },
        'commodity-producer': { band: '−10% to −30%', play: 'Copper and power-metal demand forecasts built on data-center growth get revised down.', prec: 'Copper’s 2008 demand-forecast collapse', watch: 'Grid/data-center share of demand models.' },
        'precious-metal': { band: 'flat to +20%', play: 'A tech bust that eases rates historically helps gold — the 2000–03 pattern.', prec: 'Gold bottomed in 2001 as the Nasdaq bled out, then tripled', watch: 'Fed response speed.' },
        'regulated-utility': { band: '−10% to −25%', play: 'Data-center load-growth stories priced into some utilities unwind; core regulated demand doesn’t.', prec: '—', watch: 'How much of the growth capex plan assumed AI load.' },
        'medtech': { band: '−5% to −15%', play: 'Essentially uncorrelated; falls only with the broad market beta.', prec: '2000–02: healthcare outperformed massively', watch: 'Nothing AI-specific.' },
        'turnaround': { band: '−30% to −60%', play: 'Turnarounds that pivoted TO AI lose the pivot; ones that didn’t just take market beta.', prec: 'The 1999 “internet strategy” pivot cohort', watch: 'How central AI is to the new story.' }
      } },
    { id: 'commodity-bust', name: 'Commodity collapse (−40% underlying)', theory: 'Operating leverage cuts both ways: costs are fixed, the price is not',
      cells: {
        'commodity-producer': { band: '−50% to −80%', play: 'A 40% commodity fall can erase 100% of the margin for high-cost producers — the equity moves 1.5–2.5× the commodity. Hedged, low-cost names fall half as far.', prec: '2014–16 oil bust: E&Ps −70–90%, majors −35%', watch: 'Cost curve position; hedge book; covenant headroom.' },
        'precious-metal': { band: '−40% to −70% (miners), ≈ metal (ETFs)', play: 'Miners amplify the metal 2–3× down; the ETF just tracks it.', prec: '2013: gold −28%, GDX −54%', watch: 'AISC vs spot — margin-to-zero distance.' },
        'leveraged-cyclical': { band: '−20% to −40% (if energy/construction-exposed)', play: 'Regional demand tied to the commodity economy (Texas, Alberta) rolls over with it.', prec: 'Equipment rental in the 2015–16 oil-patch bust', watch: 'Geographic revenue mix.' },
        'fortress-mega': { band: '−5% to −15%', play: 'Mostly noise; cheaper inputs can even help.', prec: '—', watch: '—' },
        'quality-large': { band: '−5% to −20%', play: 'Industrial exposure determines the hit.', prec: '2015–16 industrial soft patch', watch: 'Energy end-market share.' },
        'smallcap-industrial': { band: '−10% to −30%', play: 'Depends entirely on end-market mix.', prec: '—', watch: 'Customer concentration in the commodity patch.' },
        'semis-growth': { band: '−5% to −15%', play: 'Largely uncorrelated.', prec: '—', watch: '—' },
        'pre-profit-burner': { band: '−10% to −30%', play: 'Energy-storage burners: cheaper power weakens the arbitrage story.', prec: '—', watch: 'How the unit economics assume power prices.' },
        'micro-spec': { band: '−30% to −70% (resource micro-caps)', play: 'Exploration financing dies with the commodity price.', prec: 'TSX-V resource winters 2013–15', watch: 'Treasury vs drill-program cost.' },
        'regulated-utility': { band: 'flat to +10%', play: 'Cheaper fuel, same allowed returns — mild tailwind.', prec: '—', watch: '—' },
        'medtech': { band: 'flat', play: 'Uncorrelated.', prec: '—', watch: '—' },
        'turnaround': { band: 'varies', play: 'Only commodity-linked turnarounds care.', prec: '—', watch: '—' },
        'crypto-proxy': { band: 'mixed', play: 'Cheaper energy cuts mining costs — one of the few beneficiaries.', prec: '2020 cheap-power mining margins', watch: 'Power-purchase terms.' }
      } }
  ];

  function baseSym(sym) { return String(sym || '').toUpperCase().replace(/\.(TO|V|CN|NE|UN|U)$/, '').replace(/\.[A-Z]$/, ''); }

  function classify(sym, name, secType) {
    var b = baseSym(sym);
    if (secType === 'CURRENCY') return null;
    var key = MAP[b] || null;
    if (!key) {
      // generic fallback: ETFs → quality-large proxy; unknown equities → micro-spec if it looks tiny, else quality-large
      key = secType === 'EXCHANGE_TRADED_FUND' ? 'quality-large' : 'micro-spec';
    }
    return { arch: key, label: ARCH[key].label, desc: ARCH[key].desc, known: !!MAP[b] };
  }

  function playbook(sym, name, secType) {
    var c = classify(sym, name, secType);
    if (!c) return null;
    var out = { sym: sym, arch: c.arch, label: c.label, desc: c.desc, known: c.known, scenarios: [] };
    SCENARIOS.forEach(function (s) {
      var cell = s.cells[c.arch];
      if (cell) out.scenarios.push({ id: s.id, name: s.name, theory: s.theory, band: cell.band, play: cell.play, prec: cell.prec, watch: cell.watch });
    });
    return out;
  }

  Q.theories = { ARCH: ARCH, SCENARIOS: SCENARIOS, classify: classify, playbook: playbook, baseSym: baseSym };
})();
