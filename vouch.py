import discord

from discord.ui import View, Modal, TextInput

from datetime import datetime, timezone

from config import (
    STORE_NAME,
    VOUCH_CHANNEL_ID,
    MIN_RATING,
    MAX_RATING,
    GIF_BANNER_URL,
    LOGO_URL,
)

from database import (
    get_connection,
)


# =========================================================
# TIME
# =========================================================

def now_utc():
    return datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )


# =========================================================
# GET TICKET
# =========================================================

def get_ticket(ticket_id: int):

    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    try:
        cursor.execute(
            """
            SELECT *
            FROM tickets
            WHERE id = %s
            LIMIT 1
            """,
            (ticket_id,)
        )

        return cursor.fetchone()

    finally:
        cursor.close()
        connection.close()


# =========================================================
# CHECK ALREADY VOUCHED
# =========================================================

def has_vouched(ticket_id: int):

    connection = get_connection()

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT id
            FROM vouches
            WHERE ticket_id = %s
            LIMIT 1
            """,
            (ticket_id,)
        )

        result = cursor.fetchone()

        return result is not None

    finally:
        cursor.close()
        connection.close()


# =========================================================
# SAVE VOUCH
# =========================================================

def save_vouch(
    ticket_id: int,
    customer_id: int,
    rating: int,
    review: str,
):

    connection = get_connection()

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO vouches (
                ticket_id,
                customer_id,
                rating,
                review,
                created_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                ticket_id,
                customer_id,
                rating,
                review,
                now_utc(),
            )
        )

        # ID auto-increment dari tabel vouches
        vouch_id = cursor.lastrowid

        cursor.execute(
            """
            UPDATE tickets
            SET vouched = 1
            WHERE id = %s
            """,
            (ticket_id,)
        )

        connection.commit()

        return vouch_id

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


# =========================================================
# VOUCH MODAL
# =========================================================

class VouchModal(Modal):

    def __init__(
        self,
        ticket_id: int,
    ):

        super().__init__(
            title="Submit Vouch"
        )

        self.ticket_id = ticket_id

        # =================================================
        # RATING
        # =================================================

        self.rating = TextInput(
            label="Rating",
            placeholder="Masukkan rating 1-5",
            required=True,
            min_length=1,
            max_length=1,
        )

        # =================================================
        # REVIEW
        # =================================================

        self.review = TextInput(
            label="Review / Testimoni",
            placeholder=(
                "Ceritakan pengalaman kamu..."
            ),
            style=discord.TextStyle.paragraph,
            required=True,
            min_length=1,
            max_length=1000,
        )

        self.add_item(self.rating)
        self.add_item(self.review)

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        # =================================================
        # VALIDATE RATING
        # =================================================

        try:
            rating = int(
                self.rating.value.strip()
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ Rating harus berupa angka dari 1 sampai 5.",
                ephemeral=True
            )

            return

        if not (
            MIN_RATING
            <= rating
            <= MAX_RATING
        ):

            await interaction.response.send_message(
                (
                    f"❌ Rating harus antara "
                    f"{MIN_RATING} dan {MAX_RATING}."
                ),
                ephemeral=True
            )

            return

        # =================================================
        # GET TICKET
        # =================================================

        ticket = get_ticket(
            self.ticket_id
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ Data ticket tidak ditemukan.",
                ephemeral=True
            )

            return

        # =================================================
        # CUSTOMER CHECK
        # =================================================

        if (
            interaction.user.id
            != ticket["customer_id"]
        ):

            await interaction.response.send_message(
                "❌ Kamu bukan pemilik ticket ini.",
                ephemeral=True
            )

            return

        # =================================================
        # STATUS CHECK
        # =================================================

        if ticket["status"] != "closed":

            await interaction.response.send_message(
                "❌ Ticket ini belum ditutup.",
                ephemeral=True
            )

            return

        # =================================================
        # ALREADY VOUCHED
        # =================================================

        if (
            ticket["vouched"]
            or has_vouched(self.ticket_id)
        ):

            await interaction.response.send_message(
                (
                    "❌ Kamu sudah memberikan "
                    "vouch untuk ticket ini."
                ),
                ephemeral=True
            )

            return

        # =================================================
        # REVIEW
        # =================================================

        review = self.review.value.strip()

        if not review:

            await interaction.response.send_message(
                "❌ Review tidak boleh kosong.",
                ephemeral=True
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

        # =================================================
        # SAVE DATABASE + GENERATE VOUCH NUMBER
        # =================================================

        try:
            vouch_number = save_vouch(
                ticket_id=self.ticket_id,
                customer_id=interaction.user.id,
                rating=rating,
                review=review,
            )

        except Exception as error:

            print(
                f"❌ Gagal menyimpan vouch: {error}"
            )

            await interaction.followup.send(
                (
                    "❌ Gagal menyimpan vouch "
                    "ke database.\n\n"
                    f"`{error}`"
                ),
                ephemeral=True
            )

            return

        # =================================================
        # RATING DISPLAY
        # =================================================

        stars = "⭐" * rating

        # =================================================
        # HANDLED BY
        # =================================================

        if ticket.get("staff_id"):

            handled_by = (
                f"<@{ticket['staff_id']}>"
            )

        else:

            handled_by = "Tidak ada"

        # =================================================
        # ORDER
        # =================================================

        order_text = (
            ticket.get("order_text")
            or "Tidak dicatat"
        )

        order_text = order_text[:1024]

        # =================================================
        # TIMESTAMP
        # =================================================

        timestamp = int(
            datetime.now(
                timezone.utc
            ).timestamp()
        )

        # =================================================
        # CREATE VOUCH EMBED
        # =================================================

        embed = discord.Embed(
            title=(
                f"✨ A NEW "
                f"{STORE_NAME.upper()} VOUCH!"
            ),
            color=discord.Color.gold(),
            timestamp=datetime.now(
                timezone.utc
            ),
        )

        # =================================================
        # LOGO
        # =================================================

        if LOGO_URL:

            embed.set_author(
                name=STORE_NAME,
                icon_url=LOGO_URL,
            )

        # =================================================
        # VOUCH NUMBER
        # =================================================

        embed.add_field(
            name="Vouch No",
            value=f"**#{vouch_number:03d}**",
            inline=True,
        )

        # =================================================
        # VOUCH BY
        # =================================================

        embed.add_field(
            name="Vouch By",
            value=interaction.user.mention,
            inline=True,
        )

        # =================================================
        # ORDER
        # =================================================

        embed.add_field(
            name="Order",
            value=order_text,
            inline=True,
        )

        # =================================================
        # RATING
        # =================================================

        embed.add_field(
            name="Rating",
            value=stars,
            inline=False,
        )

        # =================================================
        # VOUCH AT
        # =================================================

        embed.add_field(
            name="Vouch At",
            value=f"<t:{timestamp}:F>",
            inline=True,
        )

        # =================================================
        # HANDLED BY
        # =================================================

        embed.add_field(
            name="Handled By",
            value=handled_by,
            inline=True,
        )

        # =================================================
        # STATUS
        # =================================================

        embed.add_field(
            name="Status",
            value="✅ Selesai",
            inline=True,
        )

        # =================================================
        # REVIEW
        # =================================================

        embed.add_field(
            name="Review",
            value=review[:1024],
            inline=False,
        )

        # =================================================
        # CUSTOMER AVATAR
        # =================================================

        try:
            embed.set_thumbnail(
                url=interaction.user.display_avatar.url
            )

        except Exception:
            pass

        # =================================================
        # BANNER
        # =================================================

        if GIF_BANNER_URL:

            embed.set_image(
                url=GIF_BANNER_URL
            )

        # =================================================
        # FOOTER
        # =================================================

        embed.set_footer(
            text=(
                f"{STORE_NAME} • "
                f"Vouch #{vouch_number:03d}"
            )
        )

        # =================================================
        # GET VOUCH CHANNEL
        # =================================================

        vouch_channel = (
            interaction.client.get_channel(
                VOUCH_CHANNEL_ID
            )
        )

        if not vouch_channel:

            try:
                vouch_channel = (
                    await interaction.client.fetch_channel(
                        VOUCH_CHANNEL_ID
                    )
                )

            except Exception as error:

                await interaction.followup.send(
                    (
                        "⚠️ Vouch berhasil disimpan "
                        "ke database, tetapi channel "
                        "vouch tidak ditemukan.\n\n"
                        f"`{error}`"
                    ),
                    ephemeral=True
                )

                return

        # =================================================
        # SEND VOUCH
        # =================================================

        try:

            await vouch_channel.send(
                embed=embed
            )

        except discord.Forbidden:

            await interaction.followup.send(
                (
                    "⚠️ Vouch berhasil disimpan, "
                    "tetapi bot tidak memiliki "
                    "permission untuk mengirim "
                    "ke channel vouch."
                ),
                ephemeral=True
            )

            return

        except discord.HTTPException as error:

            await interaction.followup.send(
                (
                    "⚠️ Vouch berhasil disimpan, "
                    "tetapi gagal mengirim embed.\n"
                    f"`{error}`"
                ),
                ephemeral=True
            )

            return

        # =================================================
        # SUCCESS
        # =================================================

        await interaction.followup.send(
            (
                "✅ **Vouch berhasil dikirim!**\n\n"
                "Terima kasih sudah mempercayai "
                f"**{STORE_NAME}** ❤️"
            ),
            ephemeral=True
        )


# =========================================================
# VOUCH VIEW
# =========================================================

class VouchDMView(View):

    def __init__(
        self,
        ticket_id: int,
    ):

        super().__init__(
            timeout=None
        )

        self.ticket_id = ticket_id

        button = discord.ui.Button(
            label="Submit Vouch",
            emoji="⭐",
            style=discord.ButtonStyle.primary,
            custom_id=f"vouch_submit:{ticket_id}",
        )

        button.callback = self.submit_vouch

        self.add_item(button)

    # =====================================================
    # SUBMIT VOUCH
    # =====================================================

    async def submit_vouch(
        self,
        interaction: discord.Interaction,
    ):

        ticket = get_ticket(
            self.ticket_id
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ Data ticket tidak ditemukan.",
                ephemeral=True
            )

            return

        if (
            interaction.user.id
            != ticket["customer_id"]
        ):

            await interaction.response.send_message(
                "❌ Vouch ini bukan milik kamu.",
                ephemeral=True
            )

            return

        if ticket["status"] != "closed":

            await interaction.response.send_message(
                "❌ Ticket ini belum ditutup.",
                ephemeral=True
            )

            return

        if (
            ticket["vouched"]
            or has_vouched(self.ticket_id)
        ):

            await interaction.response.send_message(
                (
                    "❌ Kamu sudah memberikan "
                    "vouch untuk ticket ini."
                ),
                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            VouchModal(
                ticket_id=self.ticket_id
            )
        )


# =========================================================
# GET PENDING VOUCH TICKETS
# =========================================================

def get_pending_vouch_tickets():

    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    try:
        cursor.execute(
            """
            SELECT id
            FROM tickets
            WHERE status = 'closed'
            AND vouched = 0
            """
        )

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


# =========================================================
# REGISTER PERSISTENT VOUCH VIEWS
# =========================================================

def register_vouch_views(
    bot: discord.Client,
):

    try:

        pending_tickets = (
            get_pending_vouch_tickets()
        )

    except Exception as error:

        print(
            "❌ Gagal mengambil pending vouch:"
        )

        print(error)

        return

    count = 0

    for ticket in pending_tickets:

        try:

            bot.add_view(
                VouchDMView(
                    ticket_id=ticket["id"]
                )
            )

            count += 1

        except Exception as error:

            print(
                f"❌ Gagal register vouch "
                f"ticket #{ticket['id']}: "
                f"{error}"
            )

    print(
        f"⭐ {count} pending vouch button(s) loaded."
    )


# =========================================================
# SEND VOUCH DM
# =========================================================

async def send_vouch_dm(
    user: discord.User,
    ticket_id: int,
):

    ticket = get_ticket(
        ticket_id
    )

    if not ticket:

        print(
            f"❌ Ticket #{ticket_id} tidak ditemukan."
        )

        return False

    if (
        ticket["vouched"]
        or has_vouched(ticket_id)
    ):

        return False

    # =====================================================
    # DM EMBED
    # =====================================================

    embed = discord.Embed(
        title=(
            f"⭐ Terima kasih telah menggunakan "
            f"{STORE_NAME}!"
        ),
        description=(
            "Ticket kamu telah selesai. ❤️\n\n"
            "Kami sangat menghargai kepercayaan "
            "kamu kepada kami.\n\n"
            "Bantu kami dengan memberikan "
            "rating dan review mengenai pelayanan "
            "yang kamu terima.\n\n"
            "Klik tombol di bawah untuk "
            "memberikan vouch kamu."
        ),
        color=discord.Color.gold(),
    )

    # =====================================================
    # LOGO
    # =====================================================

    if LOGO_URL:

        embed.set_author(
            name=STORE_NAME,
            icon_url=LOGO_URL,
        )

        embed.set_thumbnail(
            url=LOGO_URL
        )

    # =====================================================
    # BANNER
    # =====================================================

    if GIF_BANNER_URL:

        embed.set_image(
            url=GIF_BANNER_URL
        )

    # =====================================================
    # FOOTER
    # =====================================================

    embed.set_footer(
        text=(
            f"{STORE_NAME} • "
            f"Ticket #{ticket_id:03d}"
        )
    )

    # =====================================================
    # SEND DM
    # =====================================================

    try:

        await user.send(
            embed=embed,
            view=VouchDMView(
                ticket_id=ticket_id
            )
        )

        return True

    except discord.Forbidden:

        print(
            f"⚠️ Tidak dapat mengirim DM "
            f"ke user {user.id}."
        )

        return False

    except discord.HTTPException as error:

        print(
            f"⚠️ Gagal mengirim DM vouch "
            f"ke {user.id}: {error}"
        )

        return False