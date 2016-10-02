import json
import sys
import traceback

import tornado.gen
import tornado.web
from raven.contrib.tornado import SentryMixin

import beatmap
from common.log import logUtils as log
from common.web import requestsManager
from constants import exceptions
from helpers import osuapiHelper
from objects import glob

MODULE_NAME = "api/cacheBeatmap"
class handler(SentryMixin, requestsManager.asyncRequestHandler):
	"""
	Handler for /api/v1/cacheBeatmap
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncPost(self):
		log.warning("I BEI MEMINI DEI GRANDI CAZZI!!!")
		statusCode = 400
		data = {"message": "unknown error"}
		try:
			# Check arguments
			if requestsManager.checkArguments(self.request.arguments, ["sid", "refresh"]) == False:
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			# Get beatmap set data from osu api
			beatmapSetID = self.get_argument("sid")
			refresh = int(self.get_argument("refresh"))
			if refresh == 1:
				log.info("Forced refresh")
			apiResponse = osuapiHelper.osuApiRequest("get_beatmaps", "s={}".format(beatmapSetID), False)
			if len(apiResponse) == 0:
				raise exceptions.invalidBeatmapException

			# Loop through all beatmaps in this set and save them in db
			data["maps"] = []
			for i in apiResponse:
				log.debug("Saving beatmap {} in db".format(i["file_md5"]))
				bmap = beatmap.beatmap(i["file_md5"], int(i["beatmapset_id"]), refresh=refresh)
				pp = glob.db.fetch("SELECT pp_100 FROM beatmaps WHERE beatmap_id = %s LIMIT 1", [bmap.beatmapID])
				if pp is None:
					pp = 0
				else:
					pp = pp["pp_100"]
				data["maps"].append({
					"id": bmap.beatmapID,
					"name": bmap.songName,
					"status": bmap.rankedStatus,
					"frozen": bmap.rankedStatusFrozen,
					"pp": pp,
				})

			# Set status code and message
			statusCode = 200
			data["message"] = "ok"
		except exceptions.invalidArgumentsException:
			# Set error and message
			statusCode = 400
			data["message"] = "missing required arguments"
		except exceptions.invalidBeatmapException:
			statusCode = 400
			data["message"] = "beatmap not found from osu!api."
		except:
			log.error("Unknown error in {}!\n```{}\n{}```".format(MODULE_NAME, sys.exc_info(), traceback.format_exc()))
			if glob.sentry:
				yield tornado.gen.Task(self.captureException, exc_info=True)
		finally:
			# Add status code to data
			data["status"] = statusCode

			# Send response
			self.write(json.dumps(data))
			self.set_header("Content-Type", "application/json")
			#self.add_header("Access-Control-Allow-Origin", "*")
			self.set_status(statusCode)