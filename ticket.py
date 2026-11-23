import discord

from discord.ext import commands
from discord.ui import View, Modal, TextInput

from datetime import datetime, timezone

from config import (
    STORE_NAME,
    STAFF_ROLE_IDS,
    CHANNEL_PANEL_ID,
    TICKET_PARENT_ID,
    GIF_BANNER_URL,
    QRIS_OPTIONS,
    MAX_ACTIVE_TICKETS,
)

from database import (
    get_connection,
    has_payment,
    record_payment,
)

from logs import (
    log_ticket_created,
    log_ticket_claimed,
    log_ticket_closed,
)

from vouch import (
    send_vouch_dm,
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
# STAFF CHECK
# =========================================================

def is_staff(member: discord.Member) -> bool:

    return any(
        role.id in STAFF_ROLE_IDS
        for role in member.roles
    )


# =========================================================
# GET ACTIVE TICKETS
# =========================================================

def get_active_tickets(customer_id: int):

    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute(
        """
        SELECT *
        FROM tickets
        WHERE customer_id = %s
        AND status = 'open'
        ORDER BY id DESC
        """,
        (
            customer_id,
        )
    )

    tickets = cursor.fetchall()

    cursor.close()
    connection.close()

    return tickets


# =========================================================
# GET TICKET BY THREAD
# =========================================================

def get_ticket_by_thread(thread_id: int):

    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute(
        """
        SELECT *
        FROM tickets
        WHERE thread_id = %s
        LIMIT 1
        """,
        (
            thread_id,
        )
    )

    ticket = cursor.fetchone()

    cursor.close()
    connection.close()

    return ticket


# =========================================================
# CREATE TICKET RECORD
# =========================================================

def create_ticket_record(
    thread_id: int,
    customer_id: int,
    ticket_type: str,
    order_text: str,
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO tickets (
            thread_id,
            customer_id,
            ticket_type,
            order_text,
            status,
            created_at
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            'open',
            %s
        )
        """,
        (
            thread_id,
            customer_id,
            ticket_type,
            order_text,
            now_utc(),
        )
    )

    ticket_id = cursor.lastrowid

    connection.commit()

    cursor.close()
    connection.close()

    return ticket_id


# =========================================================
# CLOSE LOST TICKET
# =========================================================

def close_lost_ticket(ticket_id: int):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE tickets
        SET status = 'closed',
            closed_at = %s
        WHERE id = %s
        """,
        (
            now_utc(),
            ticket_id,
        )
    )

    connection.commit()

    cursor.close()
    connection.close()


# =========================================================
# ADD STAFF TO PRIVATE THREAD
# =========================================================

async def add_staff_to_thread(
    thread: discord.Thread,
    guild: discord.Guild,
):
    """
    Memasukkan semua member yang memiliki
    role Owner / Mod ke private thread.
    """

    added_ids = set()

    try:

        print(
            f"🔎 Mencari staff untuk thread: "
            f"{thread.name}"
        )

        # =================================================
        # Ambil member server dari Discord.
        # Membantu jika member belum ada di cache bot.
        # =================================================

        async for member in guild.fetch_members(
            limit=None
        ):

            # =============================================
            # Cek apakah member punya role staff
            # =============================================

            if not any(
                role.id in STAFF_ROLE_IDS
                for role in member.roles
            ):
                continue

            if member.id in added_ids:
                continue

            # =============================================
            # Tambahkan staff ke private thread
            # =============================================

            try:

                await thread.add_user(
                    member
                )

                added_ids.add(
                    member.id
                )

                print(
                    f"✅ Staff ditambahkan: "
                    f"{member} ({member.id})"
                )

            except discord.Forbidden:

                print(
                    f"❌ Tidak bisa menambahkan "
                    f"{member} ke thread."
                )

            except discord.HTTPException as error:

                print(
                    f"❌ HTTP error saat menambahkan "
                    f"{member}: {error}"
                )

        print(
            f"✅ Total staff berhasil ditambahkan: "
            f"{len(added_ids)}"
        )

    except discord.Forbidden:

        print(
            "❌ Bot tidak memiliki permission/intents "
            "untuk mengambil member server."
        )

    except discord.HTTPException as error:

        print(
            f"❌ Gagal mengambil member server: "
            f"{error}"
        )


# =========================================================
# CREATE TICKET
# =========================================================

async def create_ticket(
    interaction: discord.Interaction,
    ticket_type: str,
    order_text: str,
):

    if not interaction.guild:

        await interaction.response.send_message(
            "❌ Ticket hanya dapat dibuat di server.",
            ephemeral=True
        )

        return

    await interaction.response.defer(
        ephemeral=True
    )

    customer = interaction.user

    # =====================================================
    # CHECK ACTIVE TICKET
    # =====================================================

    active_tickets = get_active_tickets(
        customer.id
    )

    if len(active_tickets) >= MAX_ACTIVE_TICKETS:

        existing_ticket = active_tickets[0]

        existing_thread = (
            interaction.guild.get_thread(
                existing_ticket["thread_id"]
            )
        )

        if existing_thread:

            await interaction.followup.send(
                (
                    "❌ Kamu masih memiliki "
                    f"ticket aktif: {existing_thread.mention}"
                ),
                ephemeral=True
            )

            return

        close_lost_ticket(
            existing_ticket["id"]
        )

    # =====================================================
    # GET PARENT CHANNEL
    # =====================================================

    parent = interaction.guild.get_channel(
        TICKET_PARENT_ID
    )

    if not parent:

        try:

            parent = await interaction.client.fetch_channel(
                TICKET_PARENT_ID
            )

        except discord.HTTPException as error:

            await interaction.followup.send(
                (
                    "❌ Parent channel ticket "
                    "tidak ditemukan.\n\n"
                    f"ID: `{TICKET_PARENT_ID}`\n"
                    f"Error: `{error}`"
                ),
                ephemeral=True
            )

            return

    # =====================================================
    # CHECK TEXT CHANNEL
    # =====================================================

    if not isinstance(
        parent,
        discord.TextChannel
    ):

        await interaction.followup.send(
            (
                "❌ `TICKET_PARENT_ID` harus "
                "berupa Text Channel.\n\n"
                f"Channel terdeteksi: "
                f"`{type(parent).__name__}`"
            ),
            ephemeral=True
        )

        return

    # =====================================================
    # THREAD NAME
    # =====================================================

    username = (
        customer.name
        .lower()
        .replace(" ", "-")
    )

    thread_name = (
        f"{ticket_type.lower()}-{username}"
    )

    thread_name = thread_name[:100]

    # =====================================================
    # CREATE PRIVATE THREAD
    # =====================================================

    try:

        thread = await parent.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread,
            auto_archive_duration=10080,
            reason=f"{STORE_NAME} Ticket",
        )

    except discord.Forbidden:

        await interaction.followup.send(
            (
                "❌ Bot tidak memiliki permission "
                "untuk membuat Private Thread.\n\n"
                "Pastikan bot memiliki:\n"
                "• View Channel\n"
                "• Send Messages\n"
                "• Create Private Threads\n"
                "• Send Messages in Threads\n"
                "• Manage Threads"
            ),
            ephemeral=True
        )

        return

    except discord.HTTPException as error:

        await interaction.followup.send(
            (
                "❌ Gagal membuat Private Thread.\n"
                f"`{error}`"
            ),
            ephemeral=True
        )

        return

    # =====================================================
    # ADD CUSTOMER
    # =====================================================

    try:

        await thread.add_user(
            customer
        )

        print(
            f"✅ Customer ditambahkan: "
            f"{customer} ({customer.id})"
        )

    except discord.Forbidden:

        try:

            await thread.delete(
                reason="Failed to add customer"
            )

        except discord.HTTPException:
            pass

        await interaction.followup.send(
            (
                "❌ Bot tidak dapat "
                "menambahkan kamu ke ticket."
            ),
            ephemeral=True
        )

        return

    except discord.HTTPException as error:

        try:

            await thread.delete(
                reason="Failed to add customer"
            )

        except discord.HTTPException:
            pass

        await interaction.followup.send(
            (
                "❌ Gagal memasukkan kamu "
                "ke ticket.\n"
                f"`{error}`"
            ),
            ephemeral=True
        )

        return

    # =====================================================
    # ADD OWNER + MOD
    # =====================================================

    await add_staff_to_thread(
        thread,
        interaction.guild,
    )

    # =====================================================
    # CREATE DATABASE RECORD
    # =====================================================

    try:

        ticket_id = create_ticket_record(
            thread_id=thread.id,
            customer_id=customer.id,
            ticket_type=ticket_type,
            order_text=order_text[:2000],
        )

    except Exception as error:

        try:

            await thread.delete(
                reason="Failed to save ticket"
            )

        except discord.HTTPException:
            pass

        await interaction.followup.send(
            (
                "❌ Gagal menyimpan ticket "
                "ke database.\n\n"
                f"`{error}`"
            ),
            ephemeral=True
        )

        return

    # =====================================================
    # LOG CREATED
    # =====================================================

    try:

        await log_ticket_created(
            bot=interaction.client,
            ticket_id=ticket_id,
            customer_id=customer.id,
            ticket_type=ticket_type,
        )

    except Exception as error:

        print(
            f"⚠️ Ticket log created gagal: "
            f"{error}"
        )

    # =====================================================
    # TICKET EMBED
    # =====================================================

    embed = discord.Embed(
        title=f"🎫 {STORE_NAME} Ticket",
        description=(
            f"Halo {customer.mention} 👋\n\n"
            f"Ticket **{ticket_type}** kamu "
            "sudah berhasil dibuat.\n\n"
            "📦 **Kebutuhan Customer**\n"
            f"> {order_text[:2000]}\n\n"
            "Staff akan segera membantu kamu."
        ),
        color=discord.Color.from_rgb(
            47,
            49,
            54
        )
    )

    if GIF_BANNER_URL:

        embed.set_image(
            url=GIF_BANNER_URL
        )

    embed.set_footer(
        text=STORE_NAME
    )

    # =====================================================
    # SEND TICKET MESSAGE
    # =====================================================

    try:

        await thread.send(
            embed=embed,
            view=TicketControlView()
        )

    except discord.HTTPException as error:

        print(
            f"⚠️ Gagal mengirim ticket message: "
            f"{error}"
        )

    # =====================================================
    # RESPONSE
    # =====================================================

    await interaction.followup.send(
        (
            "✅ Ticket berhasil dibuat: "
            f"{thread.mention}"
        ),
        ephemeral=True
    )


# =========================================================
# CREATE TICKET MODAL
# =========================================================

class CreateTicketModal(
    Modal
):

    def __init__(
        self,
        ticket_type: str,
    ):

        super().__init__(
            title="Create Ticket"
        )

        self.ticket_type = ticket_type

        self.need = TextInput(
            label="Apa yang kamu butuhkan?",
            placeholder=(
                "Contoh: Mau beli Robux 1000"
            ),
            style=discord.TextStyle.paragraph,
            required=True,
            min_length=3,
            max_length=2000,
        )

        self.add_item(
            self.need
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        await create_ticket(
            interaction,
            self.ticket_type,
            self.need.value.strip(),
        )


# =========================================================
# QRIS PAYMENT SELECT VIEW
# =========================================================

class QRISSelectView(View):

    def __init__(self, ticket_id: int, customer_id: int):
        super().__init__(timeout=180)

        self.ticket_id = ticket_id
        self.customer_id = customer_id

        options = [
            discord.SelectOption(
                label=data["label"],
                description=data["description"],
                emoji=data["emoji"],
                value=key,
            )
            for key, data in QRIS_OPTIONS.items()
        ]

        select = discord.ui.Select(
            placeholder="Pilih QRIS tujuan pembayaran...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"payment_qris_select:{ticket_id}",
        )
        select.callback = self.select_qris
        self.add_item(select)

    async def select_qris(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ Interaksi tidak valid.",
                ephemeral=True,
            )
            return

        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Hanya staff yang dapat memilih QRIS.",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ Pilihan QRIS hanya dapat digunakan di ticket.",
                ephemeral=True,
            )
            return

        ticket = get_ticket_by_thread(interaction.channel.id)

        if not ticket or ticket["id"] != self.ticket_id:
            await interaction.response.send_message(
                "❌ Data ticket tidak cocok.",
                ephemeral=True,
            )
            return

        if ticket["status"] != "open":
            await interaction.response.send_message(
                "❌ Ticket ini sudah ditutup.",
                ephemeral=True,
            )
            return

        if has_payment(self.ticket_id):
            await interaction.response.send_message(
                "❌ Payment sudah dikonfirmasi sebelumnya.",
                ephemeral=True,
            )
            return

        selected_key = interaction.data.get("values", [None])[0]
        qris = QRIS_OPTIONS.get(selected_key)

        if not qris:
            await interaction.response.send_message(
                "❌ Pilihan QRIS tidak valid.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"💳 {qris['label']}",
            description=(
                f"Silakan lakukan pembayaran melalui **{qris['label']}**.\n\n"
                "Setelah pembayaran selesai, staff dapat menekan "
                "**Confirm Payment**."
            ),
            color=discord.Color.green(),
        )
        embed.set_image(url=qris["url"])
        embed.set_footer(text=STORE_NAME)

        await interaction.response.edit_message(
            embed=embed,
            view=PaymentConfirmView(
                ticket_id=self.ticket_id,
                customer_id=self.customer_id,
            ),
        )


# =========================================================
# PAYMENT CONFIRM VIEW
# =========================================================

class PaymentConfirmView(
    View
):

    def __init__(
        self,
        ticket_id: int,
        customer_id: int,
    ):

        super().__init__(
            timeout=None
        )

        self.ticket_id = ticket_id
        self.customer_id = customer_id

        button = discord.ui.Button(
            label="Confirm Payment",
            emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id=(
                f"payment_confirm:{ticket_id}"
            ),
        )

        button.callback = (
            self.confirm_payment
        )

        self.add_item(
            button
        )

    async def confirm_payment(
        self,
        interaction: discord.Interaction,
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):

            return

        if not is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                (
                    "❌ Hanya staff yang dapat "
                    "mengonfirmasi payment."
                ),
                ephemeral=True
            )

            return

        if not isinstance(
            interaction.channel,
            discord.Thread
        ):

            await interaction.response.send_message(
                (
                    "❌ Payment hanya dapat "
                    "dikonfirmasi di ticket."
                ),
                ephemeral=True
            )

            return

        ticket = get_ticket_by_thread(
            interaction.channel.id
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ Data ticket tidak ditemukan.",
                ephemeral=True
            )

            return

        if ticket["id"] != self.ticket_id:

            await interaction.response.send_message(
                (
                    "❌ Data payment tidak cocok "
                    "dengan ticket."
                ),
                ephemeral=True
            )

            return

        if ticket["status"] != "open":

            await interaction.response.send_message(
                "❌ Ticket ini sudah ditutup.",
                ephemeral=True
            )

            return

        if has_payment(
            self.ticket_id
        ):

            await interaction.response.send_message(
                (
                    "❌ Payment sudah "
                    "dikonfirmasi sebelumnya."
                ),
                ephemeral=True
            )

            return

        payment_id = record_payment(
            ticket_id=self.ticket_id,
            customer_id=self.customer_id,
            staff_id=interaction.user.id,
            created_at=now_utc(),
        )

        if payment_id is None:

            await interaction.response.send_message(
                (
                    "❌ Payment sudah "
                    "dicatat sebelumnya."
                ),
                ephemeral=True
            )

            return

        try:

            from logs import save_ticket_log

            save_ticket_log(
                ticket_id=self.ticket_id,
                action="payment",
                user_id=interaction.user.id,
                details=(
                    "Payment berhasil "
                    "dikonfirmasi."
                ),
            )

        except Exception as error:

            print(
                f"⚠️ Log payment gagal: "
                f"{error}"
            )

        for child in self.children:

            if isinstance(
                child,
                discord.ui.Button
            ):

                child.disabled = True

        embed = discord.Embed(
            title="✅ Payment Confirmed",
            description=(
                "Pembayaran telah dikonfirmasi oleh "
                f"{interaction.user.mention}.\n\n"
                "💰 **Payment berhasil dicatat.**"
            ),
            color=discord.Color.green()
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self,
        )


# =========================================================
# TICKET CONTROL VIEW
# =========================================================

class TicketControlView(
    View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    # =====================================================
    # CLAIM
    # =====================================================

    @discord.ui.button(
        label="Claim",
        emoji="🙋",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_claim",
    )
    async def claim_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):

            return

        if not is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                (
                    "❌ Hanya staff yang dapat "
                    "claim ticket."
                ),
                ephemeral=True
            )

            return

        if not isinstance(
            interaction.channel,
            discord.Thread
        ):

            await interaction.response.send_message(
                (
                    "❌ Tombol ini hanya dapat "
                    "digunakan di ticket thread."
                ),
                ephemeral=True
            )

            return

        ticket = get_ticket_by_thread(
            interaction.channel.id
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ Data ticket tidak ditemukan.",
                ephemeral=True
            )

            return

        if ticket["status"] != "open":

            await interaction.response.send_message(
                "❌ Ticket ini sudah ditutup.",
                ephemeral=True
            )

            return

        if ticket["staff_id"]:

            await interaction.response.send_message(
                (
                    "❌ Ticket sudah di-claim oleh "
                    f"<@{ticket['staff_id']}>."
                ),
                ephemeral=True
            )

            return

        connection = get_connection()

        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE tickets
            SET staff_id = %s,
                claimed_at = %s
            WHERE id = %s
            AND status = 'open'
            AND staff_id IS NULL
            """,
            (
                interaction.user.id,
                now_utc(),
                ticket["id"],
            )
        )

        updated = cursor.rowcount

        connection.commit()

        cursor.close()
        connection.close()

        if updated == 0:

            await interaction.response.send_message(
                (
                    "❌ Ticket baru saja "
                    "di-claim oleh staff lain."
                ),
                ephemeral=True
            )

            return

        try:

            await log_ticket_claimed(
                bot=interaction.client,
                ticket_id=ticket["id"],
                customer_id=ticket["customer_id"],
                staff_id=interaction.user.id,
                ticket_type=ticket["ticket_type"],
            )

        except Exception as error:

            print(
                f"⚠️ Ticket log claim gagal: "
                f"{error}"
            )

        await interaction.response.send_message(
            (
                "🙋 Ticket berhasil di-claim oleh "
                f"{interaction.user.mention}."
            )
        )

    # =====================================================
    # PAYMENT
    # =====================================================

    @discord.ui.button(
        label="Payment",
        emoji="💰",
        style=discord.ButtonStyle.success,
        custom_id="ticket_payment",
    )
    async def payment_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):

            return

        if not is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                (
                    "❌ Hanya staff yang dapat "
                    "membuka Payment."
                ),
                ephemeral=True
            )

            return

        if not isinstance(
            interaction.channel,
            discord.Thread
        ):

            await interaction.response.send_message(
                (
                    "❌ Tombol ini hanya dapat "
                    "digunakan di ticket."
                ),
                ephemeral=True
            )

            return

        ticket = get_ticket_by_thread(
            interaction.channel.id
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ Data ticket tidak ditemukan.",
                ephemeral=True
            )

            return

        if ticket["status"] != "open":

            await interaction.response.send_message(
                "❌ Ticket ini sudah ditutup.",
                ephemeral=True
            )

            return

        if has_payment(
            ticket["id"]
        ):

            await interaction.response.send_message(
                (
                    "❌ Payment untuk ticket ini "
                    "sudah dikonfirmasi."
                ),
                ephemeral=True
            )

            return

        embed = discord.Embed(
            title="💰 Dor's STORE Payment",
            description=(
                "Silakan pilih QRIS tujuan pembayaran di bawah ini.\n\n"
                "• 💳 QRIS Pikri\n"
                "• 💳 QRIS Epen\n"
                "• 💳 QRIS Pincen"
            ),
            color=discord.Color.green(),
        )
        embed.set_footer(text=STORE_NAME)

        await interaction.response.send_message(
            embed=embed,
            view=QRISSelectView(
                ticket_id=ticket["id"],
                customer_id=ticket["customer_id"],
            ),
        )

    # =====================================================
    # CLOSE
    # =====================================================

    @discord.ui.button(
        label="Close",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close",
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):

            return

        if not is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                (
                    "❌ Hanya staff yang dapat "
                    "menutup ticket."
                ),
                ephemeral=True
            )

            return

        if not isinstance(
            interaction.channel,
            discord.Thread
        ):

            await interaction.response.send_message(
                (
                    "❌ Tombol ini hanya dapat "
                    "digunakan di ticket."
                ),
                ephemeral=True
            )

            return

        ticket = get_ticket_by_thread(
            interaction.channel.id
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ Data ticket tidak ditemukan.",
                ephemeral=True
            )

            return

        if ticket["status"] != "open":

            await interaction.response.send_message(
                "❌ Ticket sudah ditutup.",
                ephemeral=True
            )

            return

        connection = get_connection()

        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE tickets
            SET status = 'closed',
                closed_at = %s
            WHERE id = %s
            AND status = 'open'
            """,
            (
                now_utc(),
                ticket["id"],
            )
        )

        updated = cursor.rowcount

        connection.commit()

        cursor.close()
        connection.close()

        if updated == 0:

            await interaction.response.send_message(
                (
                    "❌ Ticket baru saja "
                    "ditutup oleh staff lain."
                ),
                ephemeral=True
            )

            return

        ticket = get_ticket_by_thread(
            interaction.channel.id
        )

        if not ticket:

            await interaction.response.send_message(
                (
                    "❌ Data ticket tidak ditemukan "
                    "setelah close."
                ),
                ephemeral=True
            )

            return

        try:

            await log_ticket_closed(
                bot=interaction.client,
                ticket_id=ticket["id"],
                customer_id=ticket["customer_id"],
                staff_id=interaction.user.id,
                ticket_type=ticket["ticket_type"],
                order_text=ticket["order_text"],
            )

        except Exception as error:

            print(
                f"⚠️ Ticket log close gagal: "
                f"{error}"
            )

        await interaction.response.send_message(
            "🔒 Ticket sedang ditutup..."
        )

        # =================================================
        # SEND VOUCH DM
        # =================================================

        try:

            customer = (
                interaction.client.get_user(
                    ticket["customer_id"]
                )
            )

            if customer is None:

                try:

                    customer = (
                        await interaction.client.fetch_user(
                            ticket["customer_id"]
                        )
                    )

                except discord.HTTPException:

                    customer = None

            if customer:

                await send_vouch_dm(
                    user=customer,
                    ticket_id=ticket["id"],
                )

        except Exception as error:

            print(
                f"⚠️ Gagal mengirim DM Vouch: "
                f"{error}"
            )

        # =================================================
        # LOCK + ARCHIVE
        # =================================================

        try:

            await interaction.channel.edit(
                locked=True,
                archived=True,
                reason="Ticket closed",
            )

        except discord.Forbidden:

            print(
                "⚠️ Bot tidak memiliki permission "
                "untuk lock/archive thread."
            )

        except discord.HTTPException as error:

            print(
                f"⚠️ Gagal lock/archive thread: "
                f"{error}"
            )


# =========================================================
# TICKET PANEL
# =========================================================

class TicketPanel(
    View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    # =====================================================
    # ORDER
    # =====================================================

    @discord.ui.button(
        label="Order Ticket",
        emoji="🎟️",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_order",
    )
    async def order_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await interaction.response.send_modal(
            CreateTicketModal(
                ticket_type="Order"
            )
        )

    # =====================================================
    # SUPPORT
    # =====================================================

    @discord.ui.button(
        label="Support Ticket",
        emoji="🛠️",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_support",
    )
    async def support_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await interaction.response.send_modal(
            CreateTicketModal(
                ticket_type="Support"
            )
        )


# =========================================================
# PANEL EMBED
# =========================================================

def create_panel_embed():

    embed = discord.Embed(
        title=f"🎟️ {STORE_NAME}",
        description=(
            "Pusat Order & Layanan **Dor's STORE**\n\n"
            "Mulai pesanan kamu dengan membuat "
            "ticket order. Tim kami siap membantu "
            "proses pesanan dari awal hingga selesai.\n\n"
            "Butuh bantuan atau mengalami masalah?\n"
            "Buat ticket support dan dapatkan "
            "bantuan langsung dari tim kami."
        ),
        color=discord.Color.from_rgb(
            47,
            49,
            54,
        ),
    )

    if GIF_BANNER_URL:

        embed.set_image(
            url=GIF_BANNER_URL
        )

    embed.set_footer(
        text=STORE_NAME
    )

    return embed


# =========================================================
# SETUP TICKET
# =========================================================

def setup_ticket(
    bot: commands.Bot
):

    # =====================================================
    # !TICKET
    # =====================================================

    @bot.command(
        name="ticket"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def ticket_command(
        ctx: commands.Context
    ):

        channel = bot.get_channel(
            CHANNEL_PANEL_ID
        )

        if not channel:

            try:

                channel = await bot.fetch_channel(
                    CHANNEL_PANEL_ID
                )

            except discord.HTTPException:

                await ctx.send(
                    "❌ Channel panel ticket tidak ditemukan."
                )

                return

        if not isinstance(
            channel,
            discord.TextChannel
        ):

            await ctx.send(
                (
                    "❌ `CHANNEL_PANEL_ID` harus "
                    "berupa Text Channel."
                )
            )

            return

        await channel.send(
            embed=create_panel_embed(),
            view=TicketPanel(),
        )

        await ctx.send(
            "✅ Panel ticket berhasil dikirim."
        )

    # =====================================================
    # !TICKETTEST
    # =====================================================

    @bot.command(
        name="tickettest"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def ticket_test(
        ctx: commands.Context
    ):

        parent = bot.get_channel(
            TICKET_PARENT_ID
        )

        if parent is None:

            try:

                parent = await bot.fetch_channel(
                    TICKET_PARENT_ID
                )

            except discord.HTTPException as error:

                await ctx.send(
                    (
                        "❌ `TICKET_PARENT_ID` "
                        "tidak ditemukan.\n\n"
                        f"ID: `{TICKET_PARENT_ID}`\n"
                        f"Error: `{error}`"
                    )
                )

                return

        await ctx.send(
            (
                "🔎 **Ticket Parent Check**\n\n"
                f"**Channel:** {parent.mention}\n"
                f"**Name:** `{parent.name}`\n"
                f"**ID:** `{parent.id}`\n"
                f"**Type:** `{type(parent).__name__}`\n"
                f"**Text Channel:** "
                f"`{isinstance(parent, discord.TextChannel)}`"
            )
        )