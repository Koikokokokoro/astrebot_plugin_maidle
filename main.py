import os
import json
import random
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
import astrbot.api.message_components as Comp

@register("maidle", "Koikokokokoro", "灵感和数据来自水鱼maidle的astrbot版", "1.2.0")
class Maidle(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        base = os.getcwd()
        data_path = os.path.join(base, "data", "plugins", "maidle", "maidle.json")
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        self.songs = data.get("songs", [])
        versions = data.get("versions", [])
        self.ver_map = {item.get("version"): item.get("title") for item in versions}
        self.games = {}
        self.max_tries = 10

    @filter.command("猜歌")
    async def guess_song(self, event: AstrMessageEvent):
        raw = "".join(seg.data for seg in event.get_messages() if hasattr(seg, 'data')).strip()
        content = raw[len("猜歌"):].strip() if raw.startswith("猜歌") else raw
        group_id = str(event.get_group_id())

        # 新游戏
        if not content:
            if not self.songs:
                yield event.plain_result("未能加载 maidle.json，无法开始游戏。")
                return
            target = random.choice(self.songs)
            self.games[group_id] = {"target": target, "tries": self.max_tries}
            yield event.plain_result(f"🎵 猜歌开始！你有 {self.max_tries} 次机会，提交名称/别名/ID 来猜测。")
            return

        game = self.games.get(group_id)
        if not game:
            yield event.plain_result("请先发送 /猜歌 开始游戏。")
            return
        if game["tries"] <= 0:
            yield event.plain_result("机会已用尽，游戏结束。请重新发送 /猜歌 开始新一轮。")
            del self.games[group_id]
            return

        guess = content
        guess_song = None
        for song in self.songs:
            if (str(song.get("id")) == guess or song.get("title") == guess or guess in song.get("aliases", [])):
                guess_song = song
                break
        if not guess_song:
            game["tries"] -= 1
            yield event.plain_result(f"未找到对应曲目，剩余机会：{game['tries']}")
            return

        target = game["target"]
        # 比较
        def cmp_bool(a, b): return "✅" if a == b else "❌"
        # 读取版本标题
        def get_ver_title(v): return self.ver_map.get(v, str(v))

        checks = []
        checks.append(f"歌名: {cmp_bool(guess_song['title'], target['title'])}")
        checks.append(f"ID: {cmp_bool(guess_song['id'], target['id'])}")
        checks.append(f"曲师: {cmp_bool(guess_song.get('artist'), target.get('artist'))}")
        checks.append(f"流派: {cmp_bool(guess_song.get('genre'), target.get('genre'))}")
        gv = get_ver_title(guess_song.get('version'))
        tv = get_ver_title(target.get('version'))
        checks.append(f"版本: {cmp_bool(gv, tv)} (你: {gv}, 正确: {tv})")
        checks.append(f"BPM: {cmp_bool(guess_song.get('bpm'), target.get('bpm'))}")
        # 最高难度标准谱面
        def highest_std(song):
            stds = song.get('difficulties', {}).get('standard', [])
            return max(stds, key=lambda x: x.get('difficulty', -1)) if stds else {}
        h1 = highest_std(guess_song)
        h2 = highest_std(target)
        checks.append(f"谱师: {cmp_bool(h1.get('note_designer'), h2.get('note_designer'))}")
        checks.append(f"等级: {cmp_bool(h1.get('level'), h2.get('level'))}")

        # 构建输出
        reply = [f"🎯 猜测结果（剩余 {game['tries']} 次机会）："] + checks
        # 结果处理
        if guess_song['id'] == target['id']:
            reply.append("🎉 猜对了！游戏结束。")
            del self.games[group_id]
        else:
            game['tries'] -= 1
            if game['tries'] <= 0:
                reply.append(f"😢 机会用尽，正确答案：{target['title']} (ID {target['id']})")
                del self.games[group_id]

        yield event.plain_result("\n".join(reply))
