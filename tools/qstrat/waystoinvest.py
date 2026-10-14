"""/guides/ways-to-invest/: ways to invest, by country (AUD-32).

Dave asked (October 13, 2026) for a list of experts, how they have performed and what they promise,
then: "Give people options to invest by Country." For Canada (with Quebec), the United States, the
United Kingdom and Australia, the page sets out the kinds of help, the duty each owes by law, what it
costs, where to find and check one, how professional fund managers did against their index (S&P's
SPIVA scorecards), investor protection, tax-sheltered accounts, regulators' red flags, and a few
firms' own published prices (alphabetical, never ranked, no affiliation).

Every fact carries its source. CHECKED is the day the facts were last checked against those sources;
recheck limits each January and SPIVA figures when a new scorecard comes out (March and September).
"""
import html

from .render import DISCLAIMER

e = html.escape
CHECKED = "October 13, 2026"
PATH = "guides/ways-to-invest/"

OFFICIAL, BODY, TRADE, COMMERCIAL = "Official", "Professional body", "Trade group", "Commercial"

COUNTRIES = [
    {
        "key": "canada", "name": "Canada", "short": "Canada",
        "intro": "Amounts in Canadian dollars. Securities are regulated province by province (the Canadian Securities Administrators, CSA), "
                 "dealers and their advisors by CIRO, and in Quebec by the Autorité des marchés financiers (AMF).",
        "options": [
            {"t": "Do it yourself: an online brokerage",
             "what": "You choose and place your own trades in an order-execution-only account. It gives no recommendations.",
             "duty": "No suitability duty, because it doesn't advise you. It must be a CIRO investment dealer, and since June 1, 2022 it can't collect "
                     "trailing commissions on the funds you buy there.",
             "cost": "Many charge $0 a trade on stocks and ETFs (see the examples below). The funds' own fees still apply.",
             "src": [("AMF: investment fees", "https://lautorite.qc.ca/en/general-public/investments/tips-for-better-investments/investment-fees")]},
            {"t": "A robo-advisor (online portfolio manager)",
             "what": "Builds and runs a portfolio of ETFs for you from a questionnaire. Only registered portfolio managers and some CIRO dealers may manage money this way.",
             "duty": "The Client Focused Reforms (2021; see the full-service advisor) apply. In Ontario, a registered adviser must be responsible for the portfolio decisions.",
             "cost": "The AMF's example: about 0.5% of your money a year, plus 0.05% to 0.5% in ETF costs. A minimum fee can make it more on a small account.",
             "src": [("AMF: online advisers", "https://lautorite.qc.ca/en/general-public/investments/tips-for-better-investments/on-line-adviser"),
                     ("OSC GetSmarterAboutMoney", "https://www.getsmarteraboutmoney.ca/learning-path/working-with-an-advisor/guide-to-online-investment-advisers/")]},
            {"t": "A financial planner",
             "what": "Plans the whole picture: saving, tax, retirement, insurance, estate. \"Financial planner\" is not a securities registration; "
                     "a planner who sells investments must also be registered for that.",
             "duty": "Set by the credential and any registration. Ontario (since 2022) and Saskatchewan restrict the titles \"financial planner\" and "
                     "\"financial advisor\" to approved credentials such as FP Canada's CFP or QAFP. In Quebec the title F.Pl. needs a diploma from the "
                     "Institut de planification financière and an AMF certificate.",
             "cost": "Paid by a flat or hourly fee, by commission, by a share of assets (usually from $250,000) or by salary at a bank. "
                     "No regulator publishes a typical price.",
             "src": [("OSC: working with a planner", "https://www.getsmarteraboutmoney.ca/learning-path/making-a-plan/work-with-a-financial-planner/"),
                     ("FSRA title protection", "https://www.fsrao.ca/regulation/rules/financial-professionals-title-protection-rule"),
                     ("AMF: financial planning", "https://lautorite.qc.ca/en/becoming-a-professional/financial-planning")]},
            {"t": "A full-service advisor at a bank or dealer",
             "what": "A registered representative of an investment dealer or a mutual fund dealer who recommends investments. Regulated by CIRO "
                     "(Quebec's mutual fund representatives moved to CIRO in July 2026).",
             "duty": "The Client Focused Reforms (National Instrument 31-103): since June 30, 2021, material conflicts must be resolved in your best "
                     "interest; since December 31, 2021, suitability must put your interest first, and the firm must know its products' costs. "
                     "Regulators don't call this a fiduciary duty.",
             "cost": "The AMF lists management fees of 1% to 2.5% of your money a year. The average mutual fund cost (MER) in Canada was 1.47% "
                     "in 2023, against 0.32% for ETFs (IFIC figures).",
             "src": [("CSA: Client Focused Reforms", "https://www.securities-administrators.ca/?p=3923"),
                     ("AMF: investment fees", "https://lautorite.qc.ca/en/general-public/investments/tips-for-better-investments/investment-fees"),
                     ("Investment Executive on IFIC", "https://www.investmentexecutive.com/news/research-and-markets/fund-industry-generated-nearly-31b-from-mers-in-2023/")]},
            {"t": "A portfolio manager",
             "what": "Manages your money with discretion, buying and selling without asking each time. Registered with the provincial "
                     "regulator (the AMF in Quebec, the OSC in Ontario). Minimums are usually high.",
             "duty": "Must deal fairly, honestly and in good faith (and loyally, in Quebec). The CSA has said a fiduciary duty will virtually always "
                     "arise on a discretionary account, and Alberta, Manitoba, New Brunswick and Newfoundland and Labrador put a best-interest duty in law.",
             "cost": "Usually a percentage of the money managed. No regulator publishes a typical rate.",
             "src": [("CSA Consultation Paper 33-403", "https://osc.ca/en/SecuritiesLaw_csa_20121025_33-403_fiduciary-duty.htm")]},
        ],
        "check": [
            (OFFICIAL, "CSA National Registration Search", "https://www.securities-administrators.ca/investor-tools/are-they-registered/",
             "Whether a person or firm is registered, for what, and in which provinces (aretheyregistered.ca)."),
            (OFFICIAL, "CIRO AdvisorReport", "https://www.ciro.ca/advisor-report-search",
             "Advisors at CIRO investment dealers: registration, history and discipline. Mutual-fund-only representatives aren't in it; use the CSA search."),
            (OFFICIAL, "AMF register of firms and individuals (Quebec)", "https://lautorite.qc.ca/en/general-public/registers/register-of-firms-and-individuals-authorized-to-practice",
             "Whether someone may advise on or sell a product in Quebec. AMF information line: 1 877 525-0337."),
            (OFFICIAL, "CSA Disciplined List", "https://www.securities-administrators.ca/?p=2223",
             "Sanctions from the provincial regulators, the AMF, Quebec courts and CIRO, including past ones."),
            (BODY, "FP Canada Planner Directory", "https://fpcanada.ca/findaplanner",
             "CFP and QAFP professionals by location, and any FP Canada discipline."),
            (BODY, "Institut de planification financière directory (Quebec)", "https://institutpf.org/en/directory",
             "Quebec planners who hold the F.Pl. title."),
        ],
        "spiva": {"report": "SPIVA Canada Year-End 2025", "asof": "December 31, 2025", "url": "https://www.spglobal.com/spdji/en/spiva/article/spiva-canada",
                  "what": "Canadian equity funds that did worse than the S&P/TSX Composite",
                  "rows": [("1 year", 93.4), ("3 years", 96.3), ("5 years", 95.9), ("10 years", 98.8)],
                  "more": "U.S. equity funds sold in Canada that did worse than the S&P 500: 97.1% over 10 years."},
        "protect": [
            ("CIPF", "https://www.cipf.ca/cipf-coverage/about-cipf-coverage",
             "If a CIRO dealer fails, CIPF covers what it held for you up to $1 million for all general accounts combined (cash, margin, TFSA, FHSA), "
             "another $1 million for registered retirement accounts and another for RESPs. It doesn't cover a fall in what your investments are worth."),
            ("Quebec's Fonds d'indemnisation des services financiers", "https://www.lautorite.qc.ca/en/general-public/compensation-and-deposit-protection/submit-a-claim-to-the-fonds-dindemnisation-des-services-financiers",
             "Covers fraud or embezzlement by AMF-authorized firms and representatives, up to $200,000 a claim; investment dealers and portfolio "
             "managers were added in June 2026. Claims are due within a year of learning of the fraud. It doesn't cover investment losses."),
        ],
        "accounts": [
            ("TFSA", "https://www.canada.ca/en/revenue-agency/services/tax/registered-plans-administrators/pspa/mp-rrsp-dpsp-tfsa-limits-ympe.html",
             "$7,000 of new room in 2026, on top of unused room. Growth and withdrawals are tax-free."),
            ("RRSP", "https://www.canada.ca/en/revenue-agency/services/tax/registered-plans-administrators/pspa/mp-rrsp-dpsp-tfsa-limits-ympe.html",
             "18% of last year's earned income, up to $33,810 for 2026. Contributions are deductible; withdrawals are taxed."),
            ("FHSA", "https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/first-home-savings-account/contributing-your-fhsa.html",
             "$8,000 a year, $40,000 in all, for a first home. Deductible going in, tax-free coming out for a qualifying home."),
            ("RESP", "https://www.canada.ca/en/services/benefits/education/education-savings/estimating-amounts.html",
             "$50,000 per child in all. The federal grant adds 20% of the first $2,500 a year (up to $7,200), and Quebec's QESI adds 10% (up to $250 a year)."),
        ],
        "flags": ("Canadian Securities Administrators and AMF", [
            ("CSA: know the red flags", "https://www.securities-administrators.ca/investor-tools/avoiding-fraud/know-the-red-flags-of-fraud/"),
            ("AMF: 5 steps to avoid fraud", "https://lautorite.qc.ca/en/general-public/financial-fraud/5-steps-to-avoid-fraud")],
            ["High returns with little or no risk, or a \"guarantee\" from a person rather than an institution.",
             "Pressure to decide fast, or \"exclusive\" and insider tips.",
             "A seller who isn't registered, or a false claim of AMF approval.",
             "Fake celebrity endorsements; requests to share your screen, send more money, or pay a fee before you can withdraw."]),
        "examples": [
            ("BMO SmartFolio", "Robo-advisor", "0.70% a year on the first $100,000, falling to 0.40% on larger amounts; $1,000 minimum.",
             "https://www.bmo.com/main/personal/investments/online-investing/smartfolio/pricing/"),
            ("Desjardins Online Brokerage (Disnat)", "Online brokerage", "$0 on online stock and ETF trades.", "https://www.disnat.com/en/platforms-and-fees/pricing"),
            ("National Bank Direct Brokerage", "Online brokerage", "$0 on online stock and ETF trades.", "https://www.nbc.ca/en/direct-brokerage/pricing.html"),
            ("Questrade", "Online brokerage", "$0 on Canadian and U.S. stock and ETF trades.", "https://www.questrade.com/pricing/self-directed-commissions-plans-fees/"),
            ("Questwealth Portfolios", "Robo-advisor", "0.25% a year; 0.20% from $100,000.", "https://www.questrade.com/pricing/questwealth-portfolios-fees"),
            ("RBC InvestEase", "Robo-advisor", "0.50% a year, plus ETF costs of 0.12% to 0.25%.", "https://www.rbcinvestease.com/pricing-fees.html"),
            ("TD Direct Investing", "Online brokerage", "$9.99 a stock trade; $0 on select ETFs.", "https://www.td.com/ca/en/investing/direct-investing/pricing"),
            ("Wealthsimple", "Robo-advisor (managed)", "0.5% a year under $100,000; 0.4% from $100,000.",
             "https://help.wealthsimple.com/hc/en-ca/articles/4410783184283-Choosing-between-trading-and-managed-accounts"),
        ],
    },
    {
        "key": "us", "name": "the United States", "short": "United States",
        "intro": "Amounts in U.S. dollars. Brokers are regulated by the SEC and FINRA; investment advisers by the SEC (over $100 million managed) or their state.",
        "options": [
            {"t": "Do it yourself: an online brokerage",
             "what": "You place your own trades through a broker-dealer.",
             "duty": "Regulation Best Interest applies when the firm recommends something; trades you choose yourself fall outside it.",
             "cost": "$0 online stock and ETF commissions at the large brokers (see the examples). FINRA's reminder: free trading doesn't mean free "
                     "investing, since margin interest, options fees and other charges still apply.",
             "src": [("FINRA: fees and commissions", "https://www.finra.org/investors/investing/investing-basics/fees-commissions")]},
            {"t": "A robo-advisor",
             "what": "An automated advisory program that builds and manages a portfolio from a questionnaire.",
             "duty": "A fiduciary, like any registered investment adviser: robo-advisers must register with the SEC or their state and file Form ADV.",
             "cost": "0% to 0.25% of your money a year at the large firms in the examples, plus the funds' own costs.",
             "src": [("SEC Investor Bulletin: robo-advisers", "https://investor.gov/additional-resources/news-alerts/alerts-bulletins/investor-bulletin-robo-advisers")]},
            {"t": "A financial planner",
             "what": "Plans the whole picture. Regulated according to how the planner is registered: as an investment adviser (SEC or state) or as a broker (FINRA).",
             "duty": "A CFP professional must act in your best interest whenever giving financial advice (CFP Board's standard, enforced since June 30, 2020). "
                     "Fee-only planners are paid only by their clients.",
             "cost": "Average annual retainer $6,815 and average one-off plan $2,926, in a 2026 survey of 491 advisors (Envestnet).",
             "src": [("CFP Board standard", "https://www.cfp.net/news/2020/06/cfp-board-now-enforcing-its-strengthened-code-of-ethics-and-standards-of-conduct"),
                     ("Envestnet fee survey 2026", "https://www.envestnet.com/newsroom/press-releases/average-financial-planning-retainer-fee-surges-52-2023-industry-accelerates")]},
            {"t": "A full-service broker",
             "what": "A broker-dealer representative who recommends and carries out trades, usually paid per transaction.",
             "duty": "Regulation Best Interest (since June 30, 2020): when recommending, must act in your best interest and can't put its own interests "
                     "ahead of yours. Must give you Form CRS, a short summary of services, fees, conflicts and disciplinary history.",
             "cost": "Commissions on each trade; Form CRS sets out how the firm is paid.",
             "src": [("SEC: Regulation Best Interest and Form CRS", "https://www.sec.gov/newsroom/press-releases/2019-89")]},
            {"t": "A registered investment adviser (wealth manager)",
             "what": "Ongoing advice and portfolio management, usually for a share of the money managed.",
             "duty": "A fiduciary duty under the Investment Advisers Act of 1940 that covers the whole relationship, not just each recommendation.",
             "cost": "The average fee was 0.96% of the money managed a year in 2026, down from 1.05% in 2023 (Envestnet).",
             "src": [("Investor.gov: investment advisers", "https://www.investor.gov/introduction-investing/getting-started/working-investment-professional/investment-advisers-0"),
                     ("Envestnet fee survey 2026", "https://www.envestnet.com/newsroom/press-releases/average-financial-planning-retainer-fee-surges-52-2023-industry-accelerates")]},
        ],
        "check": [
            (OFFICIAL, "FINRA BrokerCheck", "https://brokercheck.finra.org/",
             "Licences, ten years of employment history, customer disputes and disciplinary events, for brokers and advisers."),
            (OFFICIAL, "SEC Investment Adviser Public Disclosure", "https://adviserinfo.sec.gov/",
             "Every SEC- or state-registered adviser, its people and its Form ADV."),
            (OFFICIAL, "Investor.gov background check", "https://www.investor.gov/backgroundcheck",
             "The SEC's single search across advisers and brokers."),
            (OFFICIAL, "Your state securities regulator", "https://www.nasaa.org/contact-your-regulator/securities-regulator/",
             "The North American Securities Administrators Association's directory of state regulators."),
            (BODY, "CFP Board verification and Let's Make a Plan", "https://www.cfp.net/verify",
             "Whether someone holds the CFP and any CFP Board discipline; letsmakeaplan.org finds CFP professionals by location and service."),
            (TRADE, "NAPFA Find an Advisor", "https://www.napfa.org/find-an-advisor", "Fee-only planners who are members of NAPFA."),
        ],
        "spiva": {"report": "SPIVA U.S. Mid-Year 2026", "asof": "June 30, 2026", "url": "https://www.spglobal.com/spdji/en/documents/spiva/spiva-us-mid-year-2026.pdf",
                  "what": "Large-cap funds that did worse than the S&P 500",
                  "rows": [("1 year", 78.7), ("3 years", 76.6), ("5 years", 89.3), ("10 years", 83.3), ("15 years", 90.5), ("20 years", 92.6)],
                  "more": ""},
        "protect": [
            ("SIPC", "https://www.sipc.org/for-investors/what-sipc-protects",
             "If a brokerage fails, SIPC covers up to $500,000 of what it held for you, including up to $250,000 in cash. It doesn't cover market "
             "losses or bad advice."),
        ],
        "accounts": [
            ("401(k)", "https://www.irs.gov/newsroom/401k-limit-increases-to-24500-for-2026-ira-limit-increases-to-7500",
             "$24,500 for 2026, plus $8,000 from age 50 ($11,250 at ages 60 to 63)."),
            ("Traditional IRA", "https://www.irs.gov/retirement-plans/traditional-and-roth-iras",
             "$7,500 for 2026 (plus $1,100 from age 50). Contributions may be deductible; withdrawals are taxed."),
            ("Roth IRA", "https://www.irs.gov/newsroom/401k-limit-increases-to-24500-for-2026-ira-limit-increases-to-7500",
             "The same $7,500, shared with a traditional IRA. Not deductible; qualified withdrawals are tax-free. Phases out at $153,000 to $168,000 of income (single)."),
            ("HSA", "https://www.irs.gov/irb/2025-21_IRB", "$4,400 (self-only) or $8,750 (family) for 2026, with a high-deductible health plan."),
        ],
        "flags": ("SEC and FINRA", [
            ("Investor.gov: red flags of fraud", "https://www.investor.gov/protect-your-investments/fraud/how-avoid-fraud/red-flags-investment-fraud-checklist"),
            ("FINRA: watch for red flags", "https://www.finra.org/investors/protect-your-money/watch-red-flags")],
            ["Guaranteed or high returns with little or no risk, or returns that are suspiciously steady.",
             "Pressure to act now, and unsolicited contact.",
             "A seller or product that isn't registered.",
             "Requests to pay into a personal account, by gift card or by overseas wire."]),
        "examples": [
            ("Betterment", "Robo-advisor", "0.25% a year (or $5 a month on small balances without $200 a month in deposits).", "https://betterment.com/help/fees"),
            ("Charles Schwab", "Online brokerage", "$0 online stock and ETF trades; $0.65 per options contract.", "https://www.schwab.com/pricing"),
            ("E*TRADE", "Online brokerage", "$0 online stock and ETF trades; $0.65 per options contract.", "https://us.etrade.com/home"),
            ("Fidelity", "Online brokerage", "$0 online U.S. stock and ETF trades; $0.65 per options contract; no minimum.", "https://www.fidelity.com/trading/commissions-margin-rates"),
            ("Schwab Intelligent Portfolios", "Robo-advisor", "No advisory fee; $5,000 minimum. Schwab earns from the cash it holds in the portfolio.", "https://www.schwab.com/intelligent-portfolios"),
            ("Vanguard", "Online brokerage", "$0 online stock and ETF trades.", "https://investor.vanguard.com/investing/trading-fees-commissions"),
            ("Vanguard Digital Advisor", "Robo-advisor", "0.20% a year for all-index portfolios; $100 minimum.", "https://investor.vanguard.com/advice/compare-financial-advice"),
            ("Wealthfront", "Robo-advisor", "0.25% a year.", "https://wealthfront.com/pricing"),
        ],
    },
    {
        "key": "uk", "name": "the United Kingdom", "short": "United Kingdom",
        "intro": "Amounts in pounds. Investment firms and advisers are authorised by the Financial Conduct Authority (FCA).",
        "options": [
            {"t": "Do it yourself: an investment platform",
             "what": "You choose the investments; the platform holds them and carries out your orders.",
             "duty": "The Consumer Duty (since July 31, 2023): firms must act to deliver good outcomes for retail customers. No personal recommendation, so no suitability check.",
             "cost": "Typically 0.25% to 0.35% a year on funds, or a flat monthly fee (see the examples).",
             "src": [("FCA PS22/9: Consumer Duty", "https://www.fca.org.uk/publications/policy-statements/ps22-9-new-consumer-duty")]},
            {"t": "A robo-adviser or digital wealth manager",
             "what": "Ready-made or managed portfolios chosen from a questionnaire.",
             "duty": "The suitability rules for portfolio management (COBS 9A) and the Consumer Duty.",
             "cost": "About 0.6% to 0.7% a year plus fund costs of roughly 0.14% to 0.21% at the examples below.",
             "src": [("FCA Handbook COBS 9A", "https://www.handbook.fca.org.uk/handbook/COBS/9A/")]},
            {"t": "A financial adviser, independent or restricted",
             "what": "Personal recommendations on investments and pensions.",
             "duty": "Since the Retail Distribution Review (end of 2012), advisers can't take commission from product providers. An independent adviser must "
                     "consider the whole relevant market; a restricted one must say how it's restricted. Both must recommend what is suitable for you.",
             "cost": "FCA averages, as reported by Which? in 2026: about 2.4% of the money up front and 0.8% a year ongoing, about 1.9% a year with product "
                     "and platform charges.",
             "src": [("FSA guidance GC12/03", "https://www.fca.org.uk/publication/guidance-consultation/gc12_03.pdf"),
                     ("Which?: what advice costs", "https://www.which.co.uk/money/investing/financial-advice/guides/how-much-financial-advice-costs")]},
            {"t": "A wealth manager (discretionary)",
             "what": "Runs your portfolio under a mandate you agree, buying and selling without asking each time.",
             "duty": "The suitability rules (COBS 9A) and the Consumer Duty.",
             "cost": "Usually a percentage of the money managed. There is no official typical figure.",
             "src": [("FCA Handbook COBS 9A", "https://www.handbook.fca.org.uk/handbook/COBS/9A/")]},
            {"t": "Free guidance, and the new targeted support",
             "what": "Pension Wise, from the government-backed MoneyHelper, gives free, impartial guidance on defined-contribution pension options. "
                     "Since April 6, 2026, firms with a new FCA permission may offer \"targeted support\": suggestions for groups of people in similar circumstances.",
             "duty": "Guidance and targeted support are not personal advice: neither checks what is suitable for you as an individual. Pension Wise doesn't recommend products.",
             "cost": "Pension Wise is free.",
             "src": [("MoneyHelper: Pension Wise", "https://www.moneyhelper.org.uk/en/pensions-and-retirement/pension-wise/understanding-what-pension-wise-is-and-how-to-use-it"),
                     ("FCA PS25/22: targeted support", "https://www.fca.org.uk/publications/policy-statements/ps25-22-supporting-consumers-pensions-investment-decisions-rules-targeted-support")]},
        ],
        "check": [
            (OFFICIAL, "FCA Financial Services Register", "https://register.fca.org.uk/s/",
             "Whether a firm or person is authorised, what for, and any past fines."),
            (OFFICIAL, "FCA Firm Checker", "https://www.fca.org.uk/consumers/fca-firm-checker",
             "Checks that a firm is authorised for the specific service it's offering you."),
            (OFFICIAL, "FCA Warning List", "https://www.fca.org.uk/consumers/warning-list-unauthorised-firms",
             "Firms the FCA believes are operating without permission. Not being on it proves nothing; scammers change names."),
            (OFFICIAL, "MoneyHelper retirement adviser directory", "https://directory.moneyhelper.org.uk/",
             "Regulated advisers for retirement, from the government-backed Money and Pensions Service."),
            (BODY, "Personal Finance Society: find an adviser", "https://www.thepfs.org/membership/find-an-adviser/",
             "Members of the professional body, all FCA-authorised; filter for Chartered Financial Planners."),
            (COMMERCIAL, "Unbiased", "https://unbiased.co.uk/about-unbiased", "Free to you; paid by advice firms for enquiries. Says every adviser listed is FCA-regulated."),
            (COMMERCIAL, "VouchedFor", "https://www.vouchedfor.co.uk/", "Client reviews of advisers."),
        ],
        "spiva": {"report": "SPIVA Europe Year-End 2025", "asof": "December 31, 2025", "url": "https://www.spglobal.com/spdji/en/documents/spiva/spiva-europe-year-end-2025.pdf",
                  "what": "U.K. equity funds (in pounds) that did worse than the S&P United Kingdom BMI",
                  "rows": [("1 year", 88.2), ("10 years", 93.0)],
                  "more": "Over 10 years: 94.9% of U.K. large- and mid-cap funds and 97.0% of global equity funds sold in pounds did worse than their index."},
        "protect": [
            ("FSCS", "https://www.fscs.org.uk/what-we-cover/investments/",
             "If an authorised investment firm fails, or you lose money through bad advice from one that has, the FSCS covers up to £85,000 per person per firm. "
             "It doesn't cover investments that simply perform badly. Bank deposits are covered up to £120,000 since December 1, 2025."),
        ],
        "accounts": [
            ("Stocks and shares ISA", "https://www.gov.uk/government/publications/reduction-in-the-cash-individual-savings-account-isa-limit/cash-individual-savings-account-isa-limit-reduction",
             "£20,000 a year across all ISAs in 2026-27; growth and withdrawals are tax-free. From April 6, 2027, at most £12,000 of it can go into cash for under-65s."),
            ("Lifetime ISA", "https://www.gov.uk/lifetime-isa",
             "£4,000 a year (part of the £20,000) with a 25% government bonus, up to £1,000 a year; open it before 40. A 25% charge applies to withdrawals other than for a first home, after 60 or in terminal illness."),
            ("Junior ISA", "https://www.gov.uk/junior-individual-savings-accounts/overview", "£9,000 a year for a child, who takes control at 16 and can withdraw at 18."),
            ("Pensions and SIPPs", "https://www.gov.uk/tax-on-your-private-pension",
             "Tax relief on contributions up to 100% of earnings, within a £60,000 annual allowance (less for very high incomes)."),
        ],
        "flags": ("FCA ScamSmart", [("FCA ScamSmart", "https://www.fca.org.uk/ScamSmart")],
                  ["Unexpected contact, and returns that look too good to be true.",
                   "Pressure to act fast with bonuses or time limits.",
                   "Being told you've been specially chosen and should keep it quiet, or flattery.",
                   "Claims of FCA authorisation: check them with the Firm Checker, using contact details from the register itself, not from the caller."]),
        "examples": [
            ("AJ Bell", "Investment platform", "0.25% a year (less above £250,000); £5 a share deal, £1.50 a fund deal.", "https://ajbell.co.uk/investment-platform-charges-explained"),
            ("Hargreaves Lansdown", "Investment platform", "0.35% a year on funds; shares capped at £150 a year per account; £6.95 a share deal.", "https://www.hl.co.uk/accounts/fee-changes"),
            ("Moneyfarm", "Digital wealth manager", "0.70% a year on a £20,000 example, plus fund costs of up to 0.21%.", "https://www.moneyfarm.com/uk/pricing/"),
            ("Wealthify", "Robo-adviser", "0.6% a year, plus fund costs of about 0.14% (Original plans).", "https://wealthify.com/why-invest/fees"),
        ],
    },
    {
        "key": "australia", "name": "Australia", "short": "Australia",
        "intro": "Amounts in Australian dollars. Financial services are licensed by ASIC; super funds are regulated by APRA, and self-managed super funds by the ATO.",
        "options": [
            {"t": "Do it yourself: an online broker",
             "what": "Execution-only share trading. With a CHESS-sponsored broker the shares are registered in your name under your own HIN; with a custodial one a custodian holds them for you.",
             "duty": "Must provide its services efficiently, honestly and fairly. No best interests duty, because it gives no personal advice.",
             "cost": "From about $3 to $10 a trade at the examples below.",
             "src": [("ASX: CHESS and issuer sponsorship", "https://www.asx.com.au/content/dam/asx/documents/unlinked-docs/fact-sheet-chess-sponsored-and-issuer-sponsored-holdings.pdf"),
                     ("ASIC: licensee obligations", "https://www.asic.gov.au/for-finance-professionals/afs-licensees/afs-licensee-obligations")]},
            {"t": "A robo-adviser or micro-investing app",
             "what": "Automated portfolios, or small-dollar investing through an app. The provider must hold an Australian financial services licence or act for a licensee.",
             "duty": "ASIC: the obligations for digital advice are the same as for traditional advice; the best interests duty applies when personal advice is given.",
             "cost": "About $2 to $3 a month, plus 0.15% to 0.50% a year at some of the examples below.",
             "src": [("ASIC Regulatory Guide 255", "https://download.asic.gov.au/media/vbnlotqw/rg255-published-30-august-2016-20220328.pdf")]},
            {"t": "A financial adviser",
             "what": "Personal advice from an adviser on ASIC's Financial Advisers Register.",
             "duty": "The best interests duty in section 961B of the Corporations Act (compulsory since July 1, 2013), with conflicted remuneration banned. "
                     "New advisers since 2019 need a degree, an exam and a professional year; the titles \"financial adviser\" and \"financial planner\" are restricted "
                     "to registered advisers. Ongoing fees need your written consent each year.",
             "cost": "Median ongoing advice fee $4,668 a year in 2025 (Adviser Ratings). Moneysmart's worked example: $3,500 for a statement of advice and $1,500 to put it in place.",
             "src": [("ASIC Regulatory Guide 175", "https://download.asic.gov.au/media/xdyfri0z/rg175-published-21-november-2024.pdf"),
                     ("Moneysmart: advice costs", "https://moneysmart.gov.au/financial-advice/financial-advice-costs"),
                     ("Professional Planner on Adviser Ratings", "https://www.professionalplanner.com.au/2025/08/18-pc-jump-in-ongoing-advice-fees-significantly-outpacing-inflation-ardata/")]},
            {"t": "A full-service stockbroker",
             "what": "Trades plus research or advice.",
             "duty": "Efficiently, honestly and fairly; the best interests duty when giving personal advice.",
             "cost": "Brokerage usually from about $70 to $200 a trade, often a percentage of the trade (Finder, a comparison site).",
             "src": [("Finder: choosing a stockbroker", "https://finder.com.au/share-trading/how-do-i-find-a-good-stockbroker")]},
            {"t": "Your super fund, or a self-managed super fund",
             "what": "For most people the biggest investment they have. You can choose your fund and its investment option; in an SMSF every member is a trustee.",
             "duty": "Super trustees must act in members' best financial interests. AFCA can't hear complaints against an SMSF, and an SMSF gets no government compensation for theft or fraud.",
             "cost": "The ATO's YourSuper tool shows each MySuper product's fees, returns and APRA performance-test result.",
             "src": [("Moneysmart: SMSFs", "https://moneysmart.gov.au/how-super-works/self-managed-super-fund-smsf"),
                     ("ATO YourSuper comparison", "https://ato.gov.au/yoursuper")]},
        ],
        "check": [
            (OFFICIAL, "Financial Advisers Register (ASIC, on Moneysmart)", "https://moneysmart.gov.au/financial-advice/financial-advisers-register",
             "An adviser's work history, qualifications, what they're authorised to advise on, and any bans."),
            (OFFICIAL, "Moneysmart: choosing a financial adviser", "https://moneysmart.gov.au/financial-advice/choosing-a-financial-adviser",
             "ASIC's guide: the register, the Financial Services Guide, and questions about commissions and product links."),
            (OFFICIAL, "AFCA", "https://afca.org.au/what-to-expect/complaints-we-consider",
             "The free, independent complaints scheme for advisers, brokers, fund managers and super funds (not for investment performance alone)."),
            (BODY, "Financial Advice Association Australia: find a planner", "https://find-a-planner.faaa.au/", "Advisers listed by the professional body, by state."),
        ],
        "spiva": {"report": "SPIVA Australia Mid-Year 2026", "asof": "June 30, 2026", "url": "https://www.spglobal.com/spdji/en/documents/spiva/spiva-australia-mid-year-2026.pdf",
                  "what": "Australian equity general funds that did worse than the S&P/ASX 200",
                  "rows": [("1 year", 78.9), ("3 years", 82.9), ("5 years", 81.6), ("10 years", 88.2), ("15 years", 89.0)],
                  "more": ""},
        "protect": [
            ("Compensation Scheme of Last Resort", "https://afca.org.au/cslr",
             "Since April 2, 2024, pays unpaid AFCA awards against firms that have failed, up to $150,000 a claim, for personal advice, securities dealing and credit."),
            ("National Guarantee Fund", "https://www.asx.com.au/compensation-funds",
             "Covers a few ASX broker failures, such as a trade not completed or shares transferred without authority. It doesn't cover trading losses; "
             "Australia has no general cover like Canada's CIPF or the U.S. SIPC."),
        ],
        "accounts": [
            ("Super guarantee", "https://www.ato.gov.au/businesses-and-organisations/small-business-newsroom/the-final-sg-rate-increase-is-coming-on-1-july",
             "Employers pay 12% of ordinary earnings into super since July 1, 2025."),
            ("Concessional contributions", "https://www.ato.gov.au/tax-rates-and-codes/key-superannuation-rates-and-thresholds/contributions-caps",
             "Before-tax contributions up to $30,000 in 2025-26 and $32,500 in 2026-27."),
            ("Non-concessional contributions", "https://www.ato.gov.au/tax-rates-and-codes/key-superannuation-rates-and-thresholds/contributions-caps",
             "After-tax contributions up to $120,000 in 2025-26 and $130,000 in 2026-27."),
            ("First Home Super Saver", "https://www.ato.gov.au/individuals-and-families/super-for-individuals-and-families/super/withdrawing-and-using-your-super/early-access-to-super/first-home-super-saver-scheme/about-fhss-release-amounts",
             "Voluntary contributions of up to $15,000 a year and $50,000 in all can be released toward a first home."),
        ],
        "flags": ("ASIC's Moneysmart", [("Moneysmart: check before you invest", "https://moneysmart.gov.au/check-and-report-scams/check-before-you-invest")],
                  ["No Australian financial services licence, or a claim that one isn't needed.",
                   "Repeated contact and pressure to decide quickly.",
                   "Very high promised returns, or large returns for a small deposit.",
                   "A borrowed well-known name, celebrity or social-media endorsements, or a false claim of ASIC endorsement."]),
        "examples": [
            ("CommSec", "Online broker (CHESS-sponsored)", "$5 a trade up to $1,000; $10 to $3,000; $19.95 to $10,000; $29.95 to $25,000; 0.12% above.",
             "https://www.commbank.com.au/investing/commsec-australian-shares.html"),
            ("CommSec Pocket", "Micro-investing app", "$2 a trade up to $1,000, 0.20% above; $50 minimum.", "https://www.commbank.com.au/investing/commsec-pocket.html"),
            ("Pearler", "Online broker (CHESS-sponsored)", "$6.50 a trade.", "https://Pearler.com/pricing"),
            ("Raiz", "Micro-investing app", "From $2.50 a month.", "https://raizinvest.com.au/fees"),
            ("Selfwealth", "Online broker", "$9.50 a trade.", "https://selfwealth.com.au/pricing"),
            ("Spaceship Voyager", "Micro-investing app", "$3 a month from a $100 balance, plus 0.15% to 0.50% a year by portfolio.",
             "https://help.spaceship.com.au/en/articles/5694014-what-are-the-fees-for-spaceship-voyager"),
            ("Stake", "Online broker (own HIN)", "$3 a trade up to $30,000; 0.01% above.", "https://hellostake.com/au/asx-investing"),
        ],
    },
]

# the 10-year figure from each scorecard, for the summary at the top
TEN_YEAR = [("Canada", "Canadian equity funds vs the S&P/TSX Composite", 98.8, "to Dec 2025"),
            ("United Kingdom", "U.K. equity funds vs the S&P United Kingdom BMI", 93.0, "to Dec 2025"),
            ("Australia", "Australian equity funds vs the S&P/ASX 200", 88.2, "to Jun 2026"),
            ("United States", "Large-cap funds vs the S&P 500", 83.3, "to Jun 2026")]


def _src(items):
    return " ".join(f'<a class="wti-src" href="{e(u)}" rel="noopener" target="_blank">{e(t)}</a>' for t, u in items)


def _bars(rows):
    return "".join(f'<div class="wti-bar"><span>{e(lab)}</span><i style="--w:{v:.1f}%" aria-hidden="true"></i><b>{v:.1f}%</b></div>' for lab, v in rows)


def _country(c):
    opts = "".join(f"""<div class="card wti-opt"><h3 class="h3">{e(o["t"])}</h3><p>{e(o["what"])}</p>
<dl><dt>What it must promise you</dt><dd>{e(o["duty"])}</dd><dt>What it costs</dt><dd>{e(o["cost"])}</dd></dl>
<p class="small muted">Sources: {_src(o["src"])}</p></div>""" for o in c["options"])
    check = "".join(f'<li><span class="wti-tag" data-kind="{e(kind.split()[0].lower())}">{e(kind)}</span> <a href="{e(u)}" rel="noopener" target="_blank"><b>{e(n)}</b></a>'
                    f'<span class="small muted"> {e(d)}</span></li>' for kind, n, u, d in c["check"])
    sp = c["spiva"]
    spiva = (f'<p class="small muted">{e(sp["what"])}, by period, to {e(sp["asof"])}.</p><div class="wti-bars">{_bars(sp["rows"])}</div>'
             + (f'<p class="small">{e(sp["more"])}</p>' if sp["more"] else "")
             + f'<p class="small muted">Source: {_src([(sp["report"] + ", S&P Dow Jones Indices", sp["url"])])}. The scorecards count funds that closed or merged along the way, so the figures are not flattered by the funds that survived.</p>')
    protect = "".join(f'<li><b>{e(n)}.</b> {e(t)} {_src([("Source", u)])}</li>' for n, u, t in c["protect"])
    accts = "".join(f'<li><b>{e(n)}:</b> {e(t)} {_src([("Source", u)])}</li>' for n, u, t in c["accounts"])
    who, fsrc, flags = c["flags"]
    flag_li = "".join(f"<li>{e(x)}</li>" for x in flags)
    ex = "".join(f'<tr><td><a href="{e(u)}" rel="noopener" target="_blank">{e(f)}</a></td><td>{e(k)}</td><td>{e(p)}</td></tr>' for f, k, p, u in c["examples"])
    return f"""<section class="wti-country" id="{c["key"]}" data-wti="{c["key"]}" aria-labelledby="{c["key"]}-h">
<div class="sec-head"><h2 class="h2" id="{c["key"]}-h">Ways to invest in {e(c["name"])}</h2><p>{e(c["intro"])}</p></div>
<div class="wti-opts">{opts}</div>
<div class="split">
<div class="card prose"><h3 class="h3">Find and check an expert</h3><ul class="wti-check">{check}</ul></div>
<div class="card prose"><h3 class="h3">How the professionals did</h3>{spiva}</div>
</div>
<div class="split">
<div class="card prose"><h3 class="h3">If a firm fails</h3><ul>{protect}</ul></div>
<div class="card prose"><h3 class="h3">Tax-sheltered accounts</h3><ul>{accts}</ul></div>
</div>
<div class="card prose"><h3 class="h3">What no one can promise you</h3><p>The warning signs of investment fraud, as {e(who)} list them:</p><ul>{flag_li}</ul>
<p class="small muted">Sources: {_src(fsrc)}</p></div>
<div class="card prose wti-ex"><h3 class="h3">Some firms and the prices they publish</h3>
<p class="small muted">Each firm's own published price as of {CHECKED}, in alphabetical order. These are examples, not recommendations or a ranking; Be The Puck has no affiliation with any of them and earns nothing from them. Prices change, so check the firm's page.</p>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Firm</th><th>Kind</th><th>Its published price</th></tr></thead><tbody>{ex}</tbody></table></div></div>
</section>"""


def ways_to_invest_page(site):
    path, depth = PATH, 2
    h = lambda x: site.href(depth, x)
    picker = "".join(f'<button type="button" data-wti-pick="{c["key"]}" aria-pressed="false">{e(c["short"])}</button>' for c in COUNTRIES)
    body = f"""
<nav class="crumbs"><a href="{h('guides/')}">Guides</a><span>/</span><span>Ways to invest</span></nav>
<section class="pair-head"><p class="eyebrow">Guide</p><h1 class="h1">Ways to invest, by country</h1>
<p class="lede">Be The Puck tests published trading rules on real prices. It isn't registered to advise anyone, and it doesn't know your goals, taxes or timeline. People who can are listed here, country by country: the kinds of help, what each must promise you by law, what it costs, where to check one, and how professional fund managers have done against simply owning the index.</p>
<div class="wti-pick" data-wti-root hidden><span class="small muted">Your country:</span><div class="seg" role="group" aria-label="Country">{picker}</div></div></section>

<section class="card prose wti-short"><h2 class="h3">The same four things hold in every country</h2>
<ol>
<li><b>No one can promise you a return.</b> Regulators in all four countries list high or guaranteed returns with little risk as the first warning sign of fraud.</li>
<li><b>Registration is one free search.</b> Each country's official register is listed below. In most places a title like "financial planner" doesn't mean the person is registered to sell or advise on investments.</li>
<li><b>The duty owed to you depends on the kind of help.</b> A U.S. investment adviser is a fiduciary; a U.S. broker must act in your best interest when it recommends; a Canadian dealer's advisor must put your interest first on suitability; an Australian adviser owes a best interests duty in law; a U.K. adviser can't take commission. Each country's section spells it out.</li>
<li><b>Most professional stock pickers trail their index.</b> Over ten years, S&amp;P's scorecards find most actively managed funds did worse than the index they're measured against:</li>
</ol>
<div class="wti-bars wti-top">{"".join(f'<div class="wti-bar"><span>{e(n)}<small>{e(w)}, {e(d)}</small></span><i style="--w:{v:.1f}%" aria-hidden="true"></i><b>{v:.1f}%</b></div>' for n, w, v, d in TEN_YEAR)}</div>
<p class="small muted">Share of funds that did worse than their index over the ten years to the date shown. Sources: the SPIVA scorecards linked in each country's section.</p></section>

{"".join(_country(c) for c in COUNTRIES)}

<section class="card prose"><p class="small muted">Checked against the linked sources on {CHECKED}. Rules, limits and prices change; the linked page is the authority. Be The Puck is not registered as an adviser, dealer or planner in any country, takes no payment from any firm named here, and takes no positions in the names it covers. {DISCLAIMER}</p>
<p class="small"><a href="{h('guides/your-plays/')}">How Be The Puck's own signal works</a> · <a href="{h('articles/when-to-sell/')}">When to sell: what an exit rule would have done</a> · <a href="{h('articles/one-stock-too-many/')}">One stock too many</a></p></section>
"""
    site.add(path, site.shell(path, "Ways to invest, by country: who can advise you, what they must promise, how they've done",
                              "Canada, the United States, the United Kingdom and Australia: the kinds of investment help, the duty each owes by law, what it costs, "
                              "where to check one, and how professional funds did against their index.",
                              body, active="learn/", link=False, scripts=("assets/waystoinvest.js",)))
