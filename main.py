"""
ケンタエージェント - メインエントリーポイント
Telegramボットとエージェントを統合する
"""

import logging
import asyncio
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)
from config import TELEGRAM_TOKEN, ALLOWED_USER_ID
from agent import run_agent
from scheduler import setup_scheduler
from storage import get_conversation, set_conversation, clear_conversation
from output import deliver, OutputChannel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 会話履歴は storage.py 経由（Redis移行対応済み）
# conversation_histories dict は storage.py に移動済み


# ─────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────

def is_allowed(user_id: int) -> bool:
    """アクセス制限チェック（自分以外は拒否）"""
    return ALLOWED_USER_ID == 0 or user_id == ALLOWED_USER_ID


async def safe_send(bot, chat_id: int, text: str):
    """output.pyのdeliver経由で送信（後方互換性維持）"""
    await deliver(bot, chat_id, text, OutputChannel.TELEGRAM)


# ─────────────────────────────────────────
# コマンドハンドラ
# ─────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return

    msg = (
        "🤖 *ケンタエージェント* 起動完了\n\n"
        "自然言語でなんでも指示してください。\n\n"
        "例：\n"
        "• 「ポートフォリオ全部の株価チェックして」\n"
        "• 「NVDAの最近のニュース調べて」\n"
        "• 「今日やること：〇〇をタスクに追加して」\n"
        "• 「朝レポート今すぐ出して」\n\n"
        "コマンド一覧は /help"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    msg = (
        "📋 *コマンド一覧*\n\n"
        "/start — 起動メッセージ\n"
        "/help — このヘルプ\n"
        "/clear — 会話履歴をリセット\n"
        "/morning — 朝レポートを今すぐ実行\n"
        "/portfolio — ポートフォリオ株価一括確認\n"
        "/tasks — 未完了タスク一覧\n"
        "/notes — 最近のメモ一覧\n"
        "/status — エージェント状態確認\n\n"
        "それ以外はすべて自然言語で話しかけてください 🗣"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    clear_conversation(update.effective_user.id)
    await update.message.reply_text("🧹 会話履歴をリセットしました")


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """日報を即時生成"""
    if not is_allowed(update.effective_user.id):
        return
    chat_id = update.effective_chat.id
    await update.message.reply_text("📋 日報を生成中です...少しお待ちください🙏")
    loop = asyncio.get_running_loop()
    try:
        from agent import generate_daily_report
        report = await loop.run_in_executor(None, generate_daily_report)
        await deliver(context.bot, chat_id, report, OutputChannel.TELEGRAM)
    except Exception as e:
        logger.error(f"日報エラー: {e}", exc_info=True)
        await context.bot.send_message(chat_id=chat_id, text="⚠️ 日報の生成中にエラーが発生しました")


async def cmd_morning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """朝レポートを即時実行"""
    if not is_allowed(update.effective_user.id):
        return
    chat_id = update.effective_chat.id
    await update.message.reply_text("🌅 朝レポートを生成中です...1〜2分かかります🙏")
    from scheduler import _morning_report_prompt
    from storage import save_report_cache
    loop = asyncio.get_running_loop()
    try:
        report = await loop.run_in_executor(None, lambda: run_agent(_morning_report_prompt()))
        save_report_cache("morning", report)
        await safe_send(context.bot, chat_id, report)
    except Exception as e:
        logger.error(f"朝レポートエラー: {e}", exc_info=True)
        await context.bot.send_message(chat_id=chat_id, text="⚠️ レポートの生成中にエラーが発生しました")


async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ポートフォリオ一括確認"""
    if not is_allowed(update.effective_user.id):
        return
    chat_id = update.effective_chat.id
    await update.message.reply_text("📈 ポートフォリオを確認中です...少しお待ちください🙏")
    loop = asyncio.get_running_loop()
    try:
        response = await loop.run_in_executor(
            None, lambda: run_agent("保有銘柄全銘柄の含み損益・前日比を円換算で一覧表示してください")
        )
        await safe_send(context.bot, chat_id, response)
    except Exception as e:
        logger.error(f"ポートフォリオエラー: {e}", exc_info=True)
        await context.bot.send_message(chat_id=chat_id, text="⚠️ エラーが発生しました。しばらく待ってから再試行してください")


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """タスク一覧表示"""
    if not is_allowed(update.effective_user.id):
        return
    chat_id = update.effective_chat.id
    await update.message.reply_text("📋 タスクを取得中です...🙏")
    loop = asyncio.get_running_loop()
    try:
        response = await loop.run_in_executor(
            None, lambda: run_agent("未完了のタスク一覧を表示してください")
        )
        await safe_send(context.bot, chat_id, response)
    except Exception as e:
        logger.error(f"タスクエラー: {e}", exc_info=True)
        await context.bot.send_message(chat_id=chat_id, text="⚠️ エラーが発生しました。しばらく待ってから再試行してください")


async def cmd_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """最近のメモ表示"""
    if not is_allowed(update.effective_user.id):
        return
    chat_id = update.effective_chat.id
    await update.message.reply_text("📝 メモを取得中です...🙏")
    loop = asyncio.get_running_loop()
    try:
        response = await loop.run_in_executor(
            None, lambda: run_agent("最近保存したメモを10件表示してください")
        )
        await safe_send(context.bot, chat_id, response)
    except Exception as e:
        logger.error(f"メモエラー: {e}", exc_info=True)
        await context.bot.send_message(chat_id=chat_id, text="⚠️ エラーが発生しました。しばらく待ってから再試行してください")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """エージェントステータス確認"""
    if not is_allowed(update.effective_user.id):
        return

    try:
        from scheduler import scheduler
        jobs = []
        for job in scheduler.get_jobs():
            if job.next_run_time:
                next_run = job.next_run_time.strftime("%m/%d %H:%M")
            else:
                next_run = "未定"
            jobs.append(f"• {job.id}: 次回 {next_run}")
        jobs_text = "\n".join(jobs) if jobs else "• スケジューラー未起動"
    except Exception as e:
        jobs_text = f"• 取得エラー: {str(e)}"

    history_count = len(get_conversation(update.effective_user.id))
    msg = (
        f"✅ *エージェント稼働中*\n\n"
        f"会話履歴: {history_count}件\n"
        f"定期タスク:\n{jobs_text}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ─────────────────────────────────────────
# メッセージハンドラ（自然言語）
# ─────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """テキストメッセージを受け取りエージェントに渡す"""
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("⛔ アクセス権限がありません")
        return

    user_message = update.message.text
    chat_id = update.effective_chat.id

    # 即時受信確認メッセージ（ユーザーが生死確認できるように）
    await update.message.reply_text("🏯 坂本が受け取ったき！STEVEとJOHNNYに確認させちゅう...少し待っちょれや🙏")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    history = get_conversation(user_id)

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, lambda: run_agent(user_message, history)
        )

        set_conversation(user_id, history + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": response},
        ])

        await safe_send(context.bot, chat_id, response)

    except Exception as e:
        logger.error(f"エージェントエラー: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ エラーが発生しました: {str(e)}")



# ─────────────────────────────────────────
# メイン
# ─────────────────────────────────────────

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN が設定されていません。.envを確認してください")

    async def post_init(app):
        """起動時に実行：コマンド登録＋スケジューラー起動"""
        await app.bot.set_my_commands([
            BotCommand("morning", "朝の市況レポートを今すぐ実行"),
            BotCommand("report", "日報を今すぐ確認"),
            BotCommand("portfolio", "ポートフォリオ株価確認"),
            BotCommand("tasks", "タスク一覧"),
            BotCommand("notes", "メモ一覧"),
            BotCommand("clear", "会話履歴リセット"),
            BotCommand("status", "エージェント状態"),
            BotCommand("help", "ヘルプ"),
        ])
        if ALLOWED_USER_ID:
            setup_scheduler(app.bot, ALLOWED_USER_ID)
            logger.info(f"✅ スケジューラー起動完了（送信先: {ALLOWED_USER_ID}）")

    # ApplicationBuilderのpost_initで確実に起動
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    # コマンド登録
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("morning", cmd_morning))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("portfolio", cmd_portfolio))
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("notes", cmd_notes))
    app.add_handler(CommandHandler("status", cmd_status))

    # メッセージハンドラ
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 ケンタエージェント起動")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
