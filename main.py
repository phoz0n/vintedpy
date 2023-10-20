import asyncio
import random
import os
import dataset
import dotenv
import hikari
import lightbulb
from loguru import logger as log
from langdetect import detect
from scraper import language_flags

from scraper import generate_embed, scrape

dotenv.load_dotenv()

bot = lightbulb.BotApp(token=os.getenv("TOKEN"))
db = dataset.connect("sqlite:///data.db")
table = db["subscriptions"]
language_flags = {
    "fr": "🇫🇷",
    "it": "🇮🇹",
    "en": "🇬🇧",
    "ja": "🇯🇵"
}

async def run_background() -> None:
    log.info("Scraper started.")

    while True:
        log.info("Executing scraping loop")
        for sub in db["subscriptions"]:
            print(sub)
            items = scrape(db, sub)
            log.debug("{items} found for {id}", items=len(items), id=str(sub["id"]))
            for item in items:
                embed = generate_embed(item, sub["id"])

                await bot.rest.create_message(sub["channel_id"], embed=embed)

            if len(items) > 0:
                # Update table by using last in date item timestamp
                table.update(
                    {
                        "id": sub["id"],
                        "last_sync": int(
                            items[0]["photo"]["high_resolution"]["timestamp"]
                        ),
                    },
                    ["id"],
                )

        sleep_duration = random.randint(60, 120)
        await asyncio.sleep(sleep_duration)
        log.info("Slept for {duration} seconds", duration=sleep_duration)


@bot.listen(hikari.ShardReadyEvent)
async def ready_listener(_):
    log.info("Bot is ready")
    log.info("{count} subscriptions registered", count=table.count())
    asyncio.create_task(run_background())

@bot.command()
@lightbulb.option("url", "URL to vinted search", type=str, required=True)
@lightbulb.option("channel_name", "Name of the channel for alerts", type=str, required=True)
@lightbulb.command("subscribe", "Subscribe to a Vinted search")
@lightbulb.implements(lightbulb.SlashCommand)
async def subscribe(ctx: lightbulb.Context) -> None:
    # Obtenir l'ID du serveur (guild) depuis le contexte d'interaction
    guild_id = ctx.interaction.guild_id

    if guild_id:
        # Récupérer l'objet du serveur (guild) à partir de l'ID du serveur
        guild = bot.cache.get_guild(int(guild_id))

        if guild:
            # Récupérer l'ID de la catégorie "alertes vinted" depuis les variables d'environnement
            category_id = os.getenv("CATEGORY_ID")

            if category_id:
                # Vérifier si la catégorie existe dans le serveur (guild)
                alert_category = guild.get_channel(int(category_id))

                if alert_category and isinstance(alert_category, hikari.GuildCategory):
                    # Créer un nouveau canal avec le nom spécifié sous la catégorie "alertes vinted"
                    new_channel = await guild.create_text_channel(ctx.options.channel_name, category=alert_category)

                    # Enregistrer l'abonnement dans la base de données
                    table.insert(
                        {"url": ctx.options.url, "channel_id": new_channel.id, "last_sync": -1}
                    )
                    log.info("Subscription created for {url}", url=ctx.options.url)

                    await ctx.respond(f"✅ Created subscription in #{new_channel.name} under {alert_category.name}")
                else:
                    await ctx.respond("❌ Error: Could not find the specified category by ID.")
            else:
                await ctx.respond("❌ Error: CATEGORY_ID is not defined in the environment variables.")
        else:
            await ctx.respond("❌ Error: Could not find the server (guild). Please use this command in a server (guild).")
    else:
        await ctx.respond("❌ Error: Could not obtain the server (guild) ID.")

@bot.command()
@lightbulb.command("subscriptions", "Get a list of subscription")
@lightbulb.implements(lightbulb.SlashCommand)
async def subscriptions(ctx: lightbulb.Context) -> None:
    embed = hikari.Embed(title="Subscriptions")

    for sub in table:
        embed.add_field(name="#" + str(sub["id"]), value=sub["url"])

    await ctx.respond(embed)

@bot.command()
@lightbulb.option("id", "ID of the subscription", type=int, required=True)
@lightbulb.command("unsubscribe", "Stop following a subscription")
@lightbulb.implements(lightbulb.SlashCommand)
async def unsubscribe(ctx: lightbulb.Context) -> None:
    subscription_id = ctx.options.id
    subscription = table.find_one(id=subscription_id)

    if subscription:
        # Supprimer l'alerte de la base de données
        table.delete(id=subscription_id)

        # Obtenir l'objet du canal à partir de l'ID du canal dans l'alerte
        channel = bot.cache.get_guild(ctx.interaction.guild_id).get_channel(subscription["channel_id"])

        if channel:
            # Supprimer le canal
            await channel.delete()
            log.info("Deleted subscription #{id}", id=str(subscription_id))
            await ctx.respond(f"🗑 Deleted subscription #{str(subscription_id)}.")
        else:
            await ctx.respond("❌ Error: Could not find the channel to delete.")
    else:
        await ctx.respond("❌ Error: Subscription not found with ID {id}.")

if __name__ == "__main__":
    if os.name != "nt":
        import uvloop

        uvloop.install()

    bot.run(
        activity=hikari.Activity(
            name="Vinted articles!", type=hikari.ActivityType.WATCHING
        )
    )
