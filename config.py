import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

MY_PORTFOLIO = {
    "holdings": ["B","GM","UNFI","EAT","VYM","LITE","SYF","TWLO","EZPW","DY","PARR","NEM","BLBD","INCY","APP","CLS","NEXA","MU","CRDO","TIGO","KGC","GEV","CDE"],
    "watchlist": ["NVDA","MSFT","CEG","AMD"],
    "base_currency": "JPY",
    "positions": {
        "B":    {"shares": 11, "cost_usd": 43.1518,  "name": "バリック・マイニング"},
        "GM":   {"shares": 5,  "cost_usd": 81.2580,  "name": "ゼネラル・モーターズ"},
        "UNFI": {"shares": 9,  "cost_usd": 49.2311,  "name": "ユナイテッド・ナチュラルフーズ"},
        "EAT":  {"shares": 3,  "cost_usd": 149.2233, "name": "ブリンカー・インターナショナル"},
        "VYM":  {"shares": 18, "cost_usd": 148.1188, "name": "バンガード米国高配当ETF"},
        "LITE": {"shares": 1,  "cost_usd": 898.4200, "name": "ルメンタム・ホールディングス"},
        "SYF":  {"shares": 5,  "cost_usd": 78.7160,  "name": "シンクロニー・ファイナンシャル"},
        "TWLO": {"shares": 3,  "cost_usd": 140.6900, "name": "トゥイリオ"},
        "EZPW": {"shares": 15, "cost_usd": 30.6300,  "name": "イージーコープ"},
        "DY":   {"shares": 1,  "cost_usd": 413.7400, "name": "ダイコム・インダストリーズ"},
        "PARR": {"shares": 7,  "cost_usd": 58.5171,  "name": "パー・パシフィック"},
        "NEM":  {"shares": 4,  "cost_usd": 115.2550, "name": "ニューモント"},
        "BLBD": {"shares": 6,  "cost_usd": 71.1900,  "name": "ブルー・バード"},
        "INCY": {"shares": 4,  "cost_usd": 96.8450,  "name": "インサイト"},
        "APP":  {"shares": 1,  "cost_usd": 491.0900, "name": "アップラビン"},
        "CLS":  {"shares": 1,  "cost_usd": 400.9600, "name": "セレスティカ"},
        "NEXA": {"shares": 29, "cost_usd": 15.9079,  "name": "ネクサ・リソーシズ"},
        "MU":   {"shares": 1,  "cost_usd": 461.7700, "name": "マイクロン テクノロジー"},
        "CRDO": {"shares": 2,  "cost_usd": 161.4200, "name": "クレド・テクノロジー"},
        "TIGO": {"shares": 5,  "cost_usd": 82.1840,  "name": "ミリコム"},
        "KGC":  {"shares": 13, "cost_usd": 34.4992,  "name": "キンロス・ゴールド"},
        "GEV":  {"shares": 4,  "cost_usd": 866.2650, "name": "GEベルノバ"},
        "CDE":  {"shares": 23, "cost_usd": 19.9878,  "name": "コーマイニング"},
    },
}

MORNING_REPORT_HOUR = 7
MORNING_REPORT_MINUTE = 0
MARKET_CHECK_HOUR = 23
MARKET_CHECK_MINUTE = 0

# YouTube監視チャンネル
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

YOUTUBE_CHANNELS = [
    {"name": "ばっちゃまの米国株",          "handle": "bacchama"},
    {"name": "両学長 リベラルアーツ大学",    "handle": "ryogakucho"},
    {"name": "株の買い時を考えるチャンネル", "handle": "kabunokaidoki"},
    {"name": "Makabee（ジム・クレイマー）",  "handle": "makabee7"},
    {"name": "AI仙人",                       "handle": "AI仙人ch"},
    {"name": "KEITO【AI&WEB ch】",           "handle": "keitoaiweb"},
    {"name": "けんすう@AI時代の生き方",      "handle": "kensuu"},
    {"name": "いけともch",                   "handle": "iketomo-ch"},
    {"name": "原口沙輔",                     "handle": "sasuke_haraguchi"},
]
