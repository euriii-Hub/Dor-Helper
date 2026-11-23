import discord

from datetime import datetime, timezone

from config import (
    STORE_NAME,
    CHANNEL_TICKET_LOG_ID,
)

from database import get_connection


# =========================================================
# TIME
# =========================================================

def now_utc():
    return datetime.now(timezone.utc).replace(
        tzinfo=None
    )


# =========================================================
# SAVE LOG TO DATABASE
# =========================================================

def save_ticket_log(
    ticket_id: int,
    action: str,
    user_id: int | None = None,
    details: str | None = None,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO ticket_logs (
            ticket_id,
            action,
            user_id,
            created_at,
            details
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            ticket_id,
            action,
            user_id,
            now_utc(),
            details,
        )
    )

    connection.commit()

    cursor.close()
    connection.close()


# =========================================================
# SEND DISCORD LOG
# =========================================================

async def send_ticket_log(
    bot: discord.Client,
    ticket_id: int,
    action: str,
    customer_id: int,
    staff_id: int | None = None,
    ticket_type: str | None = None,
    order_text: str | None = None,
):
    # Kalau CHANNEL_TICKET_LOG_ID = 0,
    # database log tetap tersimpan,
    # tetapi tidak dikirim ke Discord.
    if not CHANNEL_TICKET_LOG_ID:
        return

    channel = bot.get_channel(
        CHANNEL_TICKET_LOG_ID
    )

    if not channel:
        return

    # =====================================================
    # ACTION
    # =====================================================

    if action == "created":

        title = "🎫 TICKET CREATED"
        color = discord.Color.blue()

    elif action == "claimed":

        title = "🙋 TICKET CLAIMED"
        color = discord.Color.orange()

    elif action == "closed":

        title = "🔒 TICKET CLOSED"
        color = discord.Color.red()

    else:

        title = "📋 TICKET LOG"
        color = discord.Color.blurple()

    # =====================================================
    # EMBED
    # =====================================================

    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )

    embed.add_field(
        name="Customer",
        value=f"<@{customer_id}>",
        inline=True,
    )

    if staff_id:

        embed.add_field(
            name="Staff",
            value=f"<@{staff_id}>",
            inline=True,
        )

    if ticket_type:

        embed.add_field(
            name="Type",
            value=ticket_type,
            inline=True,
        )

    if order_text:

        embed.add_field(
            name="Request",
            value=order_text[:1024],
            inline=False,
        )

    embed.add_field(
        name="Ticket ID",
        value=f"`{ticket_id}`",
        inline=True,
    )

    embed.set_footer(
        text=STORE_NAME
    )

    await channel.send(
        embed=embed
    )


# =========================================================
# TICKET CREATED
# =========================================================

async def log_ticket_created(
    bot,
    ticket_id: int,
    customer_id: int,
    ticket_type: str,
):
    save_ticket_log(
        ticket_id=ticket_id,
        action="created",
        user_id=customer_id,
        details=f"Ticket type: {ticket_type}",
    )

    await send_ticket_log(
        bot=bot,
        ticket_id=ticket_id,
        action="created",
        customer_id=customer_id,
        ticket_type=ticket_type,
    )


# =========================================================
# TICKET CLAIMED
# =========================================================

async def log_ticket_claimed(
    bot,
    ticket_id: int,
    customer_id: int,
    staff_id: int,
    ticket_type: str,
):
    save_ticket_log(
        ticket_id=ticket_id,
        action="claimed",
        user_id=staff_id,
        details=f"Claimed by {staff_id}",
    )

    await send_ticket_log(
        bot=bot,
        ticket_id=ticket_id,
        action="claimed",
        customer_id=customer_id,
        staff_id=staff_id,
        ticket_type=ticket_type,
    )


# =========================================================
# TICKET CLOSED
# =========================================================

async def log_ticket_closed(
    bot,
    ticket_id: int,
    customer_id: int,
    staff_id: int | None,
    ticket_type: str,
    order_text: str | None,
):
    save_ticket_log(
        ticket_id=ticket_id,
        action="closed",
        user_id=staff_id,
        details=order_text,
    )

    await send_ticket_log(
        bot=bot,
        ticket_id=ticket_id,
        action="closed",
        customer_id=customer_id,
        staff_id=staff_id,
        ticket_type=ticket_type,
        order_text=order_text,
    )