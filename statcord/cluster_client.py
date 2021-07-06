import psutil
from collections import defaultdict

from discord.ext import commands

from statcord.client import StatcordClient, HEADERS

STAT_ENDPOINT = "https://api.statcord.com/v3/clusters"


class StatcordClusterClient(StatcordClient):
    def __init__(
        self,
        bot: commands.Bot,
        statcord_key: str,
        cluster_id: str,
        mem_stats: bool = True,
        cpu_stats: bool = True,
        net_stats: bool = True,
    ) -> None:
        super().__init__(
            bot,
            statcord_key,
            mem_stats=mem_stats,
            cpu_stats=cpu_stats,
            net_stats=net_stats
        )
        self.cluster_id = cluster_id

    async def post_stats(self) -> None:
        """Helper method used to actually post the stats to Statcord."""

        self.logger.debug("Posting stats to Statcord...")

        # mem stats
        if self.post_mem_stats:
            mem = psutil.virtual_memory()
            mem_used = str(mem.used)
            mem_load = str(mem.percent)
        else:
            mem_used = "0"
            mem_load = "0"

        # cpu stats
        if self.post_cpu_stats:
            cpu_load = str(psutil.cpu_percent())
        else:
            cpu_load = "0"

        # network stats
        if self.post_net_stats:
            net_io_counter = psutil.net_io_counters()
            total_net_usage = net_io_counter.bytes_sent + net_io_counter.bytes_recv  # current net usage
            period_net_usage = str(total_net_usage - self._prev_net_usage)  # net usage to be sent
            self._prev_net_usage = total_net_usage  # update previous net usage counter
        else:
            period_net_usage = "0"

        data = {
            "id": str(self.bot.user.id),
            "key": self.statcord_key,
            "servers": str(len(self.bot.guilds)),  # server count
            "users": str(self._get_user_count()),  # user count
            "commands": str(self._command_count),  # command count
            "active": list(self._active_users),
            "popular": [{"name": k, "count": v} for k, v in self._popular_commands.items()],  # active commands
            "memactive": mem_used,
            "memload": mem_load,
            "cpuload": cpu_load,
            "bandwidth": period_net_usage,
        }

        # reset counters
        self._popular_commands = defaultdict(int)
        self._command_count = 0
        self._active_users = set()

        # actually send the post request
        resp = await self._aiohttp_ses.post(url=STAT_ENDPOINT, json=data, headers=HEADERS)

        # handle server response
        if 500 % (resp.status + 1) == 500:
            raise Exception("Statcord server error occurred while posting stats.")
        elif resp.status == 429:
            self.logger.warning("Statcord is ratelimiting us.")
        elif resp.status != 200:
            raise Exception(f"Statcord server response status was not 200 OK:\n{await resp.text()}")
        else:
            self.logger.debug("Successfully posted stats to Statcord.")
