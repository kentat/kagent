"""
出力抽象レイヤー
================================================
現在: Telegram
将来: HTML（Webダッシュボード）/ Email

使い方:
    from output import OutputChannel, format_for_channel

    # Telegramに送信（現在のデフォルト）
    text = format_for_channel(report, OutputChannel.TELEGRAM)

    # 将来: HTMLに変換
    html = format_for_channel(report, OutputChannel.HTML)
================================================
"""

from enum import Enum


class OutputChannel(Enum):
    TELEGRAM = "telegram"
    HTML     = "html"
    EMAIL    = "email"


def format_for_channel(text: str, channel: OutputChannel = OutputChannel.TELEGRAM) -> str:
    """
    テキストを指定チャネル向けにフォーマットする

    現在はTelegramのみ実装済み。
    HTML・Emailは将来実装予定。
    """
    if channel == OutputChannel.TELEGRAM:
        return _format_telegram(text)
    elif channel == OutputChannel.HTML:
        return _format_html(text)          # 将来実装
    elif channel == OutputChannel.EMAIL:
        return _format_email(text)         # 将来実装
    return text


def _format_telegram(text: str) -> str:
    """
    Telegram向けフォーマット
    現在の実装：そのまま返す（Telegramはmarkdownをほぼそのまま表示）
    """
    return text


def _format_html(text: str) -> str:
    """
    HTML向けフォーマット（将来実装）

    実装予定:
    - Markdownを HTMLに変換
    - CSSスタイルの適用
    - 株価の上昇/下落を色付き表示
    - グラフ・チャートの埋め込み
    """
    # TODO: markdown → HTML変換
    # import markdown
    # return f"""
    # <!DOCTYPE html>
    # <html lang="ja">
    # <head>
    #   <meta charset="UTF-8">
    #   <title>Kenta Agent Report</title>
    #   <style>/* Kenta Agent スタイル */</style>
    # </head>
    # <body>
    #   {markdown.markdown(text)}
    # </body>
    # </html>
    # """
    raise NotImplementedError("HTML出力は将来実装予定です")


def _format_email(text: str) -> str:
    """
    Email向けフォーマット（将来実装）

    実装予定:
    - HTML形式のメール本文生成
    - 件名の自動生成
    - sendgrid / AWS SES 経由での送信
    """
    # TODO: Email送信実装
    # subject = _generate_subject(text)
    # html_body = _format_html(text)
    # send_via_sendgrid(subject, html_body, to=OWNER_EMAIL)
    raise NotImplementedError("Email出力は将来実装予定です")


async def deliver(bot, chat_id: int, text: str,
                  channel: OutputChannel = OutputChannel.TELEGRAM) -> None:
    """
    指定チャネルにメッセージを配信する
    将来的には複数チャネルへの同時配信もここで管理する

    Args:
        bot: Telegram bot インスタンス（Telegram以外では不使用）
        chat_id: Telegram chat ID
        text: 送信するテキスト
        channel: 出力チャネル
    """
    formatted = format_for_channel(text, channel)

    if channel == OutputChannel.TELEGRAM:
        await _deliver_telegram(bot, chat_id, formatted)
    elif channel == OutputChannel.HTML:
        await _deliver_html(formatted)         # 将来実装
    elif channel == OutputChannel.EMAIL:
        await _deliver_email(formatted)        # 将来実装


async def _deliver_telegram(bot, chat_id: int, text: str) -> None:
    """Telegramに分割して送信（4096文字制限）"""
    import asyncio
    if len(text) <= 4096:
        await bot.send_message(chat_id=chat_id, text=text)
    else:
        for i in range(0, len(text), 4096):
            await bot.send_message(chat_id=chat_id, text=text[i:i + 4096])
            await asyncio.sleep(0.3)


async def _deliver_html(text: str) -> None:
    """HTML/Webサーバーへの配信（将来実装）"""
    # TODO: WebサーバーのエンドポイントにPOST
    # async with aiohttp.ClientSession() as session:
    #     await session.post(WEB_SERVER_URL, json={"content": text})
    raise NotImplementedError("HTML配信は将来実装予定です")


async def _deliver_email(text: str) -> None:
    """Email配信（将来実装）"""
    # TODO: sendgrid / AWS SES 経由で送信
    raise NotImplementedError("Email配信は将来実装予定です")
