import os
import json
import random
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
import astrbot.api.message_components as Comp

@register("maidle", "Koikokokokoro", "从 maidle.json 随机选歌，猜测后给出比较结果", "1.9.0")
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

    @filter.command("maidle")
    async def maidle(self, event: AstrMessageEvent, content: str):
        """/maidle start | /maidle <猜测内容> | /maidle end | /maidle help 查看帮助"""
        group_id = str(event.get_group_id())
        game = self.games.get(group_id)

        # 显示帮助
        if content == "help":
            help_msg = (
                "/maidle start 开始新一轮猜歌\n"
                "/maidle <名称/别名/ID> 进行猜测\n"
                "/maidle end 结束游戏并显示答案"
            )
            yield event.plain_result(help_msg)
            return

        # 开始游戏
        if content == "start":
            if game:
                yield event.plain_result(
                    "已有游戏未结束，请使用 /maidle end 结束后再开启新一轮。"
                )
                return
            if not self.songs:
                yield event.plain_result("未能加载曲库，无法开始游戏。")
                return
            target = random.choice(self.songs)
            self.games[group_id] = {"target": target, "tries": self.max_tries}
            yield event.plain_result(
                f"🎵 Maidle 开始！你有 {self.max_tries} 次机会，使用 /maidle <名称/别名/ID> 来猜测。"
            )
            return

        # 结束游戏
        if content == "end":
            if not game:
                yield event.plain_result("当前无进行中的猜歌游戏。")
                return
            target = game["target"]
            # 使用最高难度谱面
            def select_surface(song):
                lst = []
                for t, arr in song.get('difficulties', {}).items():
                    for d in arr:
                        d['type'] = t
                        lst.append(d)
                if not lst:
                    return {}
                max_diff = max(lst, key=lambda x: x.get('difficulty', -1))
                candidates = [d for d in lst if d.get('difficulty') == max_diff.get('difficulty')]
                if len(candidates) > 1:
                    return max(candidates, key=lambda x: x.get('level_value', 0))
                return max_diff
            h_target = select_surface(target)
            # 版本标题
            def ver_title(v):
                try:
                    base = (int(v) // 100) * 100
                    return self.ver_map.get(base, str(v))
                except:
                    return str(v)
            info = (
                f"🎵 正确曲目信息：\n"
                f"标题: {target['title']}\n"
                f"ID: {target['id']}\n"
                f"曲师: {target.get('artist')}\n"
                f"流派: {target.get('genre')}\n"
                f"版本: {ver_title(target.get('version'))}\n"
                f"BPM: {target.get('bpm')}\n"
                f"谱师: {h_target.get('note_designer')}\n"
                f"等级: {h_target.get('level_value')}"
            )
            del self.games[group_id]
            yield event.plain_result(info)
            return

        # 猜歌
        if not game:
            yield event.plain_result("请先使用 /maidle start 开始游戏。")
            return
        guess = content
        # 查找曲目，不存在不扣次数
        guess_song = None
        for song in self.songs:
            if (str(song.get("id")) == guess or song.get("title") == guess or guess in song.get("aliases", [])):
                guess_song = song
                break
        if not guess_song:
            yield event.plain_result("未找到对应曲目，请检查输入。次数不扣除。")
            return

        target = game["target"]
        # 对比
        def cmp_mark(a, b): return "✅" if a == b else "❌"
        def ver_mark(gv, tv):
            try:
                gv_i, tv_i = int(gv), int(tv)
                gv_base, tv_base = (gv_i // 100) * 100, (tv_i // 100) * 100
                if gv_base == tv_base: return "✅"
                return "➡️" if gv_base < tv_base else "⬅️"
            except:
                return cmp_mark(gv, tv)
        def bpm_mark(gv, tv):
            try:
                gv_i, tv_i = int(gv), int(tv)
                if gv_i == tv_i: return "✅"
                return "⬇️" if gv_i > tv_i else "⬆️"
            except:
                return cmp_mark(gv, tv)
        def lvl_mark(g, t):
            try:
                gv, tv = float(g), float(t)
                if gv == tv: return "✅"
                return "⬇️" if gv > tv else "⬆️"
            except:
                return cmp_mark(g, t)

        # 选择
        def select_surface(song):
            lst = []
            for t, arr in song.get('difficulties', {}).items():
                for d in arr:
                    d['type'] = t
                    lst.append(d)
            if not lst:
                return {}
            max_diff = max(lst, key=lambda x: x.get('difficulty', -1))
            cands = [d for d in lst if d.get('difficulty') == max_diff.get('difficulty')]
            if len(cands) > 1:
                return max(cands, key=lambda x: x.get('level_value', 0))
            return max_diff
        h_guess = select_surface(guess_song)
        h_target = select_surface(target)

        # 谱面类型
        types_guess = []
        for t, arr in guess_song.get('difficulties', {}).items():
            if arr: types_guess.append('SD' if t=='standard' else 'DX')
        types_guess = '/'.join(types_guess)
        types_target = []
        for t, arr in target.get('difficulties', {}).items():
            if arr: types_target.append('SD' if t=='standard' else 'DX')
        types_target = '/'.join(types_target)

        # 版本
        def ver_title(v):
            try:
                base = (int(v) // 100) * 100
                return self.ver_map.get(base, str(v))
            except:
                return str(v)

        # 输出
        lines = []
        lines.append(f"歌名：{cmp_mark(guess_song['title'], target['title'])}{guess_song['title']}")
        lines.append(f"谱面类型：{cmp_mark(types_guess, types_target)}{types_guess}")
        lines.append(f"曲师：{cmp_mark(guess_song.get('artist'), target.get('artist'))}{guess_song.get('artist')}")
        lines.append(f"流派：{cmp_mark(guess_song.get('genre'), target.get('genre'))}{guess_song.get('genre')}")
        lines.append(f"版本：{ver_mark(guess_song.get('version'), target.get('version'))}{ver_title(guess_song.get('version'))}")
        lines.append(f"BPM：{bpm_mark(guess_song.get('bpm'), target.get('bpm'))}{guess_song.get('bpm')}")
        lines.append(f"谱师：{cmp_mark(h_guess.get('note_designer'), h_target.get('note_designer'))}{h_guess.get('note_designer')}")
        lines.append(f"等级：{lvl_mark(h_guess.get('level_value'), h_target.get('level_value'))}{h_guess.get('level_value')}")

        # 扣次数及结束判断
        if guess_song['id'] != target['id']:
            game['tries'] -= 1
        header = f"🎯 猜测结果（剩余 {game['tries']} 次机会）："
        if guess_song['id'] == target['id']:
            footer = "🎉 猜对了！游戏结束。"
            del self.games[group_id]
        elif game['tries'] <= 0:
            footer = f"😢 机会用尽。答案：{target['title']}"
            del self.games[group_id]
        else:
            footer = None

        msg = header + "\n" + "\n".join(lines)
        if footer:
            msg += "\n" + footer
        yield event.plain_result(msg)
