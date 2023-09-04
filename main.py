import disnake
from disnake.ext import commands, tasks
import json
import os
import time
import random
import asyncio
import numpy as np
import keep_alive
import datetime
import numpy as np
import psutil

intents = disnake.Intents.default()
intents.typing = False
intents.presences = False
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)
bot.start_time = datetime.datetime.utcnow()  # Сохраняем момент запуска бота


ping_emojis = {
    'low': '<:low_ping:1134121975862808681>',
    'medium': '<:medium_ping:1134121971525894224>',
    'high': '<:high_ping:1134121974591914004>'
}

@bot.command(
    name='ping',
    description='Проверить пинг бота к серверу'
)
async def ping(ctx):
    ping = bot.latency

    ping_intervals = np.clip(ping, [0, 0.1, 0.2], [0.1, 0.2, 100])
    ping_category = ['low', 'medium', 'high'][np.argmax(ping_intervals)]

    ping_emoji = ping_emojis.get(ping_category, '🔳')

    current_time = datetime.datetime.utcnow()  # Используем текущее время в UTC временной зоне
    
    uptime = current_time - bot.start_time  # Вычисляем время работы бота с момента запуска
    uptime_str = str(uptime)

    guild_count = len(bot.guilds)

    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    disk_usage = psutil.disk_usage('/')

    embed = disnake.Embed(
        title="Пинг и информация о боте",
        description=f"Пинг: {ping_emoji} `{ping * 1000:.0f}ms`\n"
                    f"Время работы: {uptime_str}\n"
                    f"Загруженность CPU: {cpu_percent}%\n"
                    f"Используется памяти: {memory.percent}%\n"
                    f"Свободно места на диске: {disk_usage.free / (1024 ** 3):.2f} GB / {disk_usage.total / (1024 ** 3):.2f} GB\n"
                    f"Загружено на {guild_count} серверах",
        color=disnake.Color.blue()
    )
    embed.set_footer(text="© Florida Project")

    await ctx.send(embed=embed)

# Создаем текстовый канал для тренировки капчи
async def create_captcha_channel(member):
    guild = member.guild
    channel_name = f'{member.name}-captcha-training'
    
    # Проверяем, существует ли канал для данного пользователя
    existing_channel = disnake.utils.get(guild.text_channels, name=channel_name)
    
    if existing_channel:
        return existing_channel
    
    # Создаем канал с ограничениями доступа
    overwrites = {
        guild.default_role: disnake.PermissionOverwrite(read_messages=False),
        member: disnake.PermissionOverwrite(read_messages=True, send_messages=True),
        bot.user: disnake.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    
    channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
    
    # Отправляем приветственное сообщение
    welcome_message = await channel.send(
        f'Добро пожаловать, {member.mention}!\n'
        'Это ваш канал для тренировки капчи. Нажмите на реакцию "🔔", '
        'когда будете готовы начать.'
    )
    await welcome_message.add_reaction('🔔')
    
    return channel

# Функция для проверки реакции "🔔"
def check_bell_reaction(reaction, user):
    return str(reaction.emoji) == '🔔' and user != bot.user

# Команда /training
@bot.slash_command(name='training', description='Начать тренировку капчи')
async def training(ctx: disnake.ApplicationCommandInteraction):
    member = ctx.author
    await ctx.send(f'{member.mention}, Перейдите через все каналы чтобы начать.')

    
    # Создаем текстовый канал для тренировки капчи
    captcha_channel = await create_captcha_channel(member)
    
    # Ожидаем, пока пользователь нажмет на реакцию "🔔"
    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=300.0, check=check_bell_reaction)
    except asyncio.TimeoutError:
        await captcha_channel.send('Время ожидания истекло.')
        await captcha_channel.delete()
    else:
        await asyncio.sleep(1)  # Добавьте задержку в 1 секунду
        await reaction.clear()
        await captcha_channel.send(
            'Тренировка началась! Введите 10 капчей, каждая из 5 цифр.'
        )
        
        # Собираем ответы пользователя на капчи и время ввода
        captcha_answers = []
        captcha_times = {}
        for i in range(10):
            captcha = ''.join(random.choices('0123456789', k=5))
            captcha_message = await captcha_channel.send(
                f'Капча #{i + 1}: Введите капчу: `{captcha}`'
            )
            start_time = time.time()
            try:
                message = await bot.wait_for(
                    'message',
                    timeout=300.0,
                    check=lambda m: m.channel == captcha_channel and m.author == member
                )
            except asyncio.TimeoutError:
                await captcha_message.edit(content=f'Время ожидания ответа на капчу #{i + 1} истекло.')
            else:
                if len(message.content) != 5 or not message.content.isdigit():
                    await captcha_message.edit(content=f'Некорректный формат капчи #{i + 1}. Пожалуйста, введите 5 цифр.')
                else:
                    user_captcha = message.content
                    correct = all(user_captcha[j] == captcha[j] for j in range(5))
                    if correct:
                        captcha_answers.append(user_captcha)
                        end_time = time.time()
                        captcha_times[i + 1] = end_time - start_time
                        await captcha_message.edit(content=f'Капча #{i + 1}: Верно ✅')
                    else:
                        await captcha_message.edit(content=f'Капча #{i + 1}: Неверно ❌')
                    await asyncio.sleep(1)
                    await message.delete(delay=1)
        
        # Показываем результаты тренировки
        score = len(captcha_answers)
        medals = get_medals(score)
        result_embed = disnake.Embed(
            title='Результаты тренировки',
            description=f'{member.mention}, вы успешно решили {score} капч(и): {medals}',
            color=disnake.Color.green()
        )
        await captcha_channel.send(embed=result_embed)
        
        # Выводим лучшие результаты по времени
        sorted_times = sorted(captcha_times.items(), key=lambda x: x[1])
        top_times_embed = disnake.Embed(
            title='Лучшие результаты по времени',
            color=disnake.Color.gold()
        )
        for i, (captcha_num, time_taken) in enumerate(sorted_times):
            top_times_embed.add_field(
                name=f'Капча #{captcha_num}',
                value=f'{time_taken:.2f} сек',
                inline=False
            )
        await captcha_channel.send(embed=top_times_embed)
        
        # Завершаем тренировку и удаляем канал через 30 секунд
        await captcha_channel.set_permissions(member, read_messages=True, send_messages=False)
        await captcha_channel.set_permissions(bot.user, read_messages=True, send_messages=True)
        await captcha_channel.send('Тренировка капчи завершена. Канал будет удален через 30 секунд.')
        await asyncio.sleep(30)
        await captcha_channel.delete()

# Функция для выдачи медалей в зависимости от результата
def get_medals(score):
    medals = ''
    if score == 10:
        medals += '🥇 Золотая медаль'
    elif score >= 5:
        medals += '🥈 Серебряная медаль'
    return medals

# Создаем директорию для файлов данных, если она не существует
if not os.path.exists('user_data'):
    os.makedirs('user_data')

# Функция для загрузки данных пользователя из файла
def load_user_data(user_id):
    file_path = f'user_data/{user_id}.json'
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)
    else:
        return {'balance': 0, 'last_work': None}

# Функция для сохранения данных пользователя в файл
def save_user_data(user_id, user_data):
    file_path = f'user_data/{user_id}.json'
    with open(file_path, 'w') as file:
        json.dump(user_data, file)

# Загрузка данных о пользователях из JSON-файла при запуске бота
try:
    with open('data.json', 'r') as file:
        data = json.load(file)
except FileNotFoundError:
    data = {}

# Сохранение данных о пользователях в JSON-файл при выключении бота
@bot.event
async def on_disconnect():
    with open('data.json', 'w') as file:
        json.dump(data, file)

# Команда /work с кулдауном на 24 часа
@bot.slash_command(name='work', description='Заработать Demidov coinsы')
async def work(ctx):
    user_id = str(ctx.author.id)
    user_data = load_user_data(user_id)
    
    last_work = user_data.get('last_work', None)
    if last_work is not None:
        last_work = datetime.datetime.fromisoformat(last_work)
        time_difference = datetime.datetime.now() - last_work
        if time_difference.total_seconds() < 24 * 60 * 60:
            time_left = 24 * 60 * 60 - time_difference.total_seconds()
            hours_left = int(time_left / 3600)
            minutes_left = int((time_left % 3600) / 60)
            seconds_left = int(time_left % 60)
            await ctx.send(f'Вы уже работали сегодня. Попробуйте снова через {hours_left} ч. {minutes_left} мин. {seconds_left} сек.')
            return

    earnings = random.randint(20, 150)
    user_data['balance'] += earnings
    user_data['last_work'] = datetime.datetime.now().isoformat()
    save_user_data(user_id, user_data)

    await ctx.send(f'Вы заработали {earnings} Demidov coins!')

# Команда /balance для проверки баланса пользователя
@bot.slash_command(name='balance', description='Проверить баланс')
async def balance(ctx):
    user_id = str(ctx.author.id)
    user_data = load_user_data(user_id)
    balance = user_data['balance']
    await ctx.send(f'Ваш баланс: {balance} Demidov coins')

# Команда /checkbalance для просмотра баланса другого пользователя
@bot.slash_command(name='checkbalance', description='Проверить баланс другого пользователя')
async def check_balance(ctx, member: disnake.Member):
    user_id = str(member.id)
    user_data = load_user_data(user_id)
    balance = user_data['balance']
    await ctx.send(f'Баланс {member.mention}: {balance} Demidov coins')

#редакт баланса
@bot.slash_command(name='setbalance', description='Установить баланс другого пользователя')
@commands.has_permissions(administrator=True)
async def set_balance(ctx, member: disnake.Member, new_balance: int):
    user_id = str(member.id)
    user_data = load_user_data(user_id)

    if new_balance >= 0:
        user_data['balance'] += new_balance
        message = f'Баланс {member.mention} успешно увеличен на {new_balance} Demidov coins'
    else:
        user_data['balance'] -= abs(new_balance)
        message = f'Баланс {member.mention} успешно уменьшен на {abs(new_balance)} Demidov coins'

    save_user_data(user_id, user_data)
    
    # Создаем встроенное сообщение (embed) с результатом операции
    embed = disnake.Embed(title="Изменение баланса", color=disnake.Color.blue())
    embed.add_field(name="Действие:", value=message)
    embed.add_field(name="Новый баланс:", value=user_data['balance'], inline=False)

    await ctx.send(embed=embed)

@bot.slash_command(name='pay', description='Передать Demidov coinsы другому пользователю')
async def pay(ctx, target_user: disnake.User, amount: int):
    sender_user = ctx.author

    # Проверяем, чтобы отправитель не был тем же самым пользователем
    if sender_user.id == target_user.id:
        await ctx.send('Вы не можете передать Demidov coinsы самому себе.')
        return

    # Проверяем, есть ли отправитель и получатель в базе данных балансов
    sender_balance = load_user_data(sender_user.id)['balance']
    if sender_balance < amount:
        await ctx.send(f'У вас недостаточно Demidov coins для этой операции. Ваш баланс: {sender_balance} Demidov coins.')
        return

    # Проверяем, чтобы сумма была положительной
    if amount <= 0:
        await ctx.send('Сумма для перевода должна быть положительным числом.')
        return

    # Вычитаем сумму у отправителя и добавляем получателю
    sender_balance -= amount
    target_balance = load_user_data(target_user.id)['balance']
    target_balance += amount

    # Сохраняем новые балансы в базе данных
    save_user_data(sender_user.id, {'balance': sender_balance})
    save_user_data(target_user.id, {'balance': target_balance})

    # Отправляем сообщение об успешной операции
    await ctx.send(f'{sender_user.mention} передал {target_user.mention} {amount} Demidov conins. Теперь ваш баланс: {sender_balance} Demidov conins, {target_user.mention}: {target_balance} Demidov conins.')



# Функция для начисления 1 Demidov coinsы за каждое сообщение от пользователя
@bot.event
async def on_message(message):
    if not message.author.bot:
        user_id = str(message.author.id)
        user_data = load_user_data(user_id)
        user_data['balance'] += 1
        save_user_data(user_id, user_data)

    await bot.process_commands(message)

# Таймер для ежечасного получения Demidov coins
@tasks.loop(hours=1)
async def hourly_income():
    for user_id in data.keys():
        earnings = random.randint(10, 50)
        data[user_id]['balance'] = data[user_id].get('balance', 0) + earnings

@hourly_income.before_loop
async def before_hourly_income():
    await bot.wait_until_ready()
    now = datetime.datetime.now()
    next_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    delay = (next_hour - now).total_seconds()
    await asyncio.sleep(delay)

hourly_income.start()

# Уведомление PayDay каждый час
@tasks.loop(hours=1)
async def payday_notification():
    payday_channel_id = 1144935950074527788  # Замените на ID текстового канала для уведомлений о PayDay
    payday_channel = bot.get_channel(payday_channel_id)

    if payday_channel:
        await payday_channel.send('PayDay! Всем участникам начислены зарплаты!')

@payday_notification.before_loop
async def before_payday_notification():
    await bot.wait_until_ready()
    now = datetime.datetime.now()
    next_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    delay = (next_hour - now).total_seconds()
    await asyncio.sleep(delay)

payday_notification.start()


keep_alive.keep_alive()

bot.run("secret-token")
