import os
import re
import json
import discord
from discord.ext import commands

# ==========================
# CONFIGURAÇÕES BÁSICAS
# ==========================

TOKEN = os.getenv("MTQ0NDg5NTI3Njk4Nzk3MzczNA.GqE1qw.sRWLZjauauZU4jWCrccI73fN0P2Nnoi5NoeNVQ")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # essencial para ver membros e nicks

bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================
# HIERARQUIA E PREFIXOS
# ==========================

RANKS_ORDER = [
    "REC",       # Recruta
    "AL",        # Aluno
    "CB",        # Cabo
    "3SGT",      # 3° Sargento
    "2SGT",      # 2° Sargento
    "1SGT",      # 1° Sargento
    "ST",        # Subtenente
    "ASP",       # Aspirante
    "2TEN",      # Segundo Tenente
    "1TEN",      # Primeiro Tenente
    "CAP",       # Capitão
    "MAJ",       # Major
    "TCEL",      # Tenente-Coronel
    "CEL",       # Coronel
    "SUB.CMD.G", # Sub Comando Geral
    "CMDG",      # Comandante-Geral
]

RANK_NAMES = {
    "REC": "Recruta",
    "AL": "Aluno",
    "CB": "Cabo",
    "3SGT": "3° Sargento",
    "2SGT": "2° Sargento",
    "1SGT": "1° Sargento",
    "ST": "Subtenente",
    "ASP": "Aspirante",
    "2TEN": "Segundo Tenente",
    "1TEN": "Primeiro Tenente",
    "CAP": "Capitão",
    "MAJ": "Major",
    "TCEL": "Tenente-Coronel",
    "CEL": "Coronel",
    "SUB.CMD.G": "Sub Comando Geral",
    "CMDG": "Comandante-Geral",
}

CONFIG_FILE = "config_hierarquia.json"

default_config = {
    "painel_channel_id": None,
    "painel_message_id": None,
    "logs_channel_id": None,
}

config = default_config.copy()


def load_config():
    global config
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        save_config()


def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


load_config()

# ==========================
# FUNÇÕES AUXILIARES
# ==========================


def detectar_prefixo(nome: str):
    """
    Tenta detectar o prefixo no nome.
    Aceita formatos:
    - [CB] Nome
    - [ CB ] Nome
    - CB Nome
    - REC - Nome
    Retorna (prefixo, nome_limpo) ou (None, nome_original).
    """
    original = nome

    # 1) Padrão com colchetes [CB] ou [ CB ]
    match = re.match(r"^\s*\[\s*([A-Z.]+)\s*\]\s*(.+)$", nome)
    if match:
        prefixo = match.group(1).upper()
        resto = match.group(2).strip()
        if prefixo in RANKS_ORDER:
            return prefixo, resto

    # 2) Padrão sem colchete: "CB Nome", "REC Nome"
    match = re.match(r"^\s*([A-Z.]+)\s+(.+)$", nome)
    if match:
        prefixo = match.group(1).upper()
        resto = match.group(2).strip()
        if prefixo in RANKS_ORDER:
            return prefixo, resto

    # 3) Não achou prefixo
    return None, original.strip()


async def normalizar_nick(membro: discord.Member):
    """
    Garante que o nick fique no formato [PREFIXO] Nome.
    Se não tiver prefixo → mantém como está.
    """
    display_name = membro.display_name
    prefixo, resto = detectar_prefixo(display_name)

    if prefixo is None:
        # sem prefixo reconhecido, não mexe
        return None

    nick_correto = f"[{prefixo}] {resto}"

    if nick_correto != display_name:
        try:
            await membro.edit(nick=nick_correto, reason="Normalização de prefixo hierárquico")
        except discord.Forbidden:
            print(f"Sem permissão para mudar nick de {membro}")
        except discord.HTTPException:
            print(f"Erro HTTP ao mudar nick de {membro}")
    return prefixo


def rank_level(prefixo: str):
    """Retorna o índice da hierarquia (quanto menor, mais baixo)."""
    try:
        return RANKS_ORDER.index(prefixo)
    except ValueError:
        return len(RANKS_ORDER) + 1


async def atualizar_painel(guild: discord.Guild):
    """
    Atualiza a mensagem fixa com a hierarquia atual (modelo B: lista simples).
    """
    canal_id = config.get("painel_channel_id")
    msg_id = config.get("painel_message_id")

    if not canal_id:
        return

    canal = guild.get_channel(canal_id)
    if canal is None:
        return

    # montar dicionário: prefixo -> lista de mentions
    membros_por_rank = {p: [] for p in RANKS_ORDER}

    for membro in guild.members:
        prefixo, _ = detectar_prefixo(membro.display_name)
        if prefixo in RANKS_ORDER:
            membros_por_rank[prefixo].append(membro.mention)

    texto = "📋 **HIERARQUIA ATUAL**\n\n"

    for prefixo in RANKS_ORDER:
        nome_rank = RANK_NAMES.get(prefixo, prefixo)
        lista = membros_por_rank.get(prefixo, [])
        if not lista:
            continue
        texto += f"**{prefixo} – {nome_rank}**\n"
        for mention in lista:
            texto += f"• {mention}\n"
        texto += "\n"

    # se ninguém tiver rank ainda
    if texto.strip() == "📋 **HIERARQUIA ATUAL**":
        texto += "_Nenhum membro hierarquizado ainda._"

    try:
        if msg_id:
            msg = await canal.fetch_message(msg_id)
            await msg.edit(content=texto)
        else:
            msg = await canal.send(texto)
            config["painel_message_id"] = msg.id
            save_config()
    except discord.NotFound:
        # mensagem apagada → recria
        msg = await canal.send(texto)
        config["painel_message_id"] = msg.id
        save_config()
    except discord.HTTPException as e:
        print(f"Erro ao atualizar painel: {e}")


async def logar(guild: discord.Guild, texto: str):
    canal_id = config.get("logs_channel_id")
    if not canal_id:
        return
    canal = guild.get_channel(canal_id)
    if canal is None:
        return
    try:
        await canal.send(texto)
    except discord.HTTPException:
        pass

# ==========================
# EVENTOS
# ==========================


@bot.event
async def on_ready():
    print(f"Bot logado como {bot.user} (id: {bot.user.id})")
    print("Pronto para uso!")


@bot.event
async def on_member_join(membro: discord.Member):
    """
    Quando alguém entra:
    - Se possível, define nick como [REC] NomeAtual
    - Atualiza painel
    - Loga entrada
    """
    # Se já tiver um nick, usa. Se não, usa o name
    base_name = membro.nick or membro.name
    novo_nick = f"[REC] {base_name}"

    try:
        await membro.edit(nick=novo_nick, reason="Entrada no servidor - setado como Recruta")
        await logar(membro.guild, f"👤 Novo membro: {membro.mention} setado como **REC – Recruta**.")
    except discord.Forbidden:
        print(f"Sem permissão para mudar nick de {membro}")
    except discord.HTTPException:
        print(f"Erro HTTP ao mudar nick de {membro}")

    await atualizar_painel(membro.guild)


@bot.event
async def on_member_update(antes: discord.Member, depois: discord.Member):
    """
    Detecta mudança de nick e ajusta:
    - normaliza para [PREFIXO] Nome
    - se mudar de um prefixo para outro: loga promoção/rebaixamento
    - atualiza painel
    """
    if antes.nick == depois.nick and antes.display_name == depois.display_name:
        return

    # detectar prefixo antes e depois
    prefixo_antigo, _ = detectar_prefixo(antes.display_name)
    prefixo_novo, _ = detectar_prefixo(depois.display_name)

    # normaliza nick atual
    prefixo_normalizado = await normalizar_nick(depois)
    if prefixo_normalizado:
        prefixo_novo = prefixo_normalizado

    # se não houver mudança de prefixo, só atualiza painel
    if prefixo_antigo == prefixo_novo:
        await atualizar_painel(depois.guild)
        return

    # loga mudanças relevantes
    if prefixo_antigo is None and prefixo_novo is not None:
        await logar(
            depois.guild,
            f"✅ {depois.mention} agora é **{prefixo_novo} – {RANK_NAMES.get(prefixo_novo, prefixo_novo)}**."
        )
    elif prefixo_antigo is not None and prefixo_novo is None:
        await logar(
            depois.guild,
            f"⚠ {depois.mention} removeu o prefixo hierárquico (antes era **{prefixo_antigo}**)."
        )
    elif prefixo_antigo is not None and prefixo_novo is not None:
        lvl_antigo = rank_level(prefixo_antigo)
        lvl_novo = rank_level(prefixo_novo)

        if lvl_novo > lvl_antigo:
            tipo = "📈 PROMOÇÃO"
        elif lvl_novo < lvl_antigo:
            tipo = "📉 REBAIXAMENTO"
        else:
            tipo = "ℹ ALTERAÇÃO DE PATENTE"

        await logar(
            depois.guild,
            f"{tipo}\n{depois.mention}: **{prefixo_antigo} → {prefixo_novo}**"
        )

    await atualizar_painel(depois.guild)

# ==========================
# COMANDOS
# ==========================


@bot.command(name="setpainel")
@commands.has_permissions(administrator=True)
async def setpainel(ctx, canal: discord.TextChannel):
    """
    Define o canal onde o painel de hierarquia ficará fixo.
    Uso: !setpainel #canal
    """
    config["painel_channel_id"] = canal.id
    config["painel_message_id"] = None  # vai criar uma nova
    save_config()

    await ctx.send(f"✅ Painel de hierarquia será exibido em {canal.mention}.")
    await atualizar_painel(ctx.guild)


@bot.command(name="setlogs")
@commands.has_permissions(administrator=True)
async def setlogs(ctx, canal: discord.TextChannel):
    """
    Define o canal de logs de promoções/alterações.
    Uso: !setlogs #canal
    """
    config["logs_channel_id"] = canal.id
    save_config()
    await ctx.send(f"✅ Canal de logs definido como {canal.mention}.")


@bot.command(name="hierarquia")
async def hierarquia_cmd(ctx):
    """
    Mostra a lista de patentes em ordem.
    """
    texto = "📋 **HIERARQUIA – ORDEM DE PATENTES**\n\n"
    for i, p in enumerate(RANKS_ORDER, start=1):
        texto += f"{i}. {p} – {RANK_NAMES.get(p, p)}\n"
    await ctx.send(texto)


@bot.command(name="cargo")
async def cargo_cmd(ctx, membro: discord.Member = None):
    """
    Mostra o cargo (prefixo) reconhecido pelo bot.
    Uso: !cargo @membro
    Se não passar membro, usa o autor.
    """
    if membro is None:
        membro = ctx.author

    prefixo, resto = detectar_prefixo(membro.display_name)

    if prefixo is None:
        await ctx.send(f"{membro.mention} não tem prefixo hierárquico reconhecido.")
    else:
        nome_rank = RANK_NAMES.get(prefixo, prefixo)
        await ctx.send(
            f"{membro.mention} está como **{prefixo} – {nome_rank}**\n"
            f"Nick base: `{resto}`"
        )


@bot.command(name="syncall")
@commands.has_permissions(administrator=True)
async def syncall_cmd(ctx):
    """
    Reanalisa todos os membros do servidor,
    normalizando nicks e atualizando o painel.
    """
    await ctx.send("🔄 Sincronizando hierarquia de todos os membros...")
    for membro in ctx.guild.members:
        await normalizar_nick(membro)
    await atualizar_painel(ctx.guild)
    await ctx.send("✅ Sincronização concluída.")


# INICIAR BOT
bot.run("MTQ0NDg5NTI3Njk4Nzk3MzczNA.GqE1qw.sRWLZjauauZU4jWCrccI73fN0P2Nnoi5NoeNVQ")