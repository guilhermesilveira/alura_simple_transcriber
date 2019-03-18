import io
import os

import ffmpy

class Transcriptor:

	def __init__(self, basename, basefolder="../"):
		self.basefolder = basefolder
		self.basename = basename

	def phase1_video_to_audio(self):
		output = '{}data/processed/{}.wav'.format(self.basefolder, self.basename)
		if os.path.isfile(output):
			print("Skipping {}".format(output))
			return
		ff = ffmpy.FFmpeg(
			inputs={'{}data/raw/{}.mp4'.format(self.basefolder, self.basename): None},
			outputs={output: '-ar 16000 -ac 1'}
		)
		print(ff.cmd)
		return ff.run()

	def phase2_upload_audio(self):
		"""Uploads a file to the bucket."""

		# from google.cloud import storage
		from google.cloud import storage
		
		source_file_name = '{}data/processed/{}.wav'.format(self.basefolder, self.basename)
		print("Sending {} to the cloud".format(source_file_name))

		bucket_name = "transcription-processed-wav"
		destination_blob_name = '{}.wav'.format(self.basename)

		storage_client = storage.Client()
		bucket = storage_client.get_bucket(bucket_name)
		blob = bucket.blob(destination_blob_name)

		blob.upload_from_filename(source_file_name)

		print('File {} uploaded to {}.'.format(
			source_file_name,
			destination_blob_name))
		return destination_blob_name

	def phase3_transcribe(self):
		"""Asynchronously transcribes the audio file specified by the gcs_uri."""
		from google.cloud import speech
		from google.cloud.speech import enums
		from google.cloud.speech import types
		client = speech.SpeechClient()

		gcs_uri = "gs://transcription-processed-wav/{}.wav".format(self.basename)
		print('Transcribing {}'.format(gcs_uri))

		audio = types.RecognitionAudio(uri=gcs_uri)
		config = types.RecognitionConfig(
			encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
			sample_rate_hertz=16000,
			language_code='pt-BR',
			max_alternatives=1,
			enable_word_time_offsets=True,
			enable_automatic_punctuation=True)

		operation = client.long_running_recognize(config, audio)

		print('Waiting for operation to complete...')
		response = operation.result(timeout=5*60)

		# Each result is for a consecutive portion of the audio. Iterate through
		# them to get the transcripts for the entire audio file.
		for result in response.results:
			# The first alternative is the most likely one for this portion.
			print(u'Transcript: {}'.format(result.alternatives[0].transcript))
			print('Confidence: {}'.format(result.alternatives[0].confidence))

		return TranscriptionResult(self.basename, response, basefolder=self.basefolder)

def short_transcribe(file_name):

	# Instantiates a client
	from google.cloud import speech
	client = speech.SpeechClient()

	# Imports the Google Cloud client library
	from google.cloud.speech import enums
	from google.cloud.speech import types

	# The name of the audio file to transcribe)
	input_file = '{}data/processed/{}.wav'.format(self.basefolder, file_name)
	print("Reading {}".format(input_file))

	# Loads the audio into memory
	with io.open(input_file, 'rb') as audio_file:
		content = audio_file.read()
		audio = types.RecognitionAudio(content=content)

	config = types.RecognitionConfig(
		encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
		sample_rate_hertz=16000,
		language_code='pt-BR',
		max_alternatives=1,
		enable_word_time_offsets=True,
		enable_automatic_punctuation=True)

	# Detects speech in the audio file
	response = client.recognize(config, audio)

	for result in response.results:
		print('Transcript: {}'.format(result.alternatives[0].transcript))

	return TranscriptionResult(file_name, response, basefolder=self.basefolder)

class TranscriptionResult:
	
	def __init__(self, basename, response, basefolder = '../'):
		self.basefolder = basefolder
		self.basename = basename
		self.response = response

	def time_for(self, time):
		obj = {
			'nanos' : time.nanos,
			'seconds' : 0
		}
		if time.seconds:
			obj['seconds'] = time.seconds
		return obj

	def word_for(self, word):
		return {
			'start_time' : self.time_for(word.start_time),
			'end_time' : self.time_for(word.end_time),
			'word' : word.word
		}

	def alternative_to_dict(self, alternative):
		words = list(map(self.word_for, alternative.words))
		return {
			'transcript' : alternative.transcript,
			'confidence' : alternative.confidence,
			'words' : words
		}

	def first_alternative(self, result):
		return result.alternatives[0]

	from operator import attrgetter

	def to_dict(self):
		alternatives = map(self.first_alternative, self.response.results)
		return list(map(self.alternative_to_dict, alternatives))
	
	def to_json(self):
		import simplejson as json
		obj = self.to_dict()
		return json.dumps(obj, sort_keys=True, indent=4)

	def save_json(self):
		import simplejson as json
		output = '{}reports/{}.json'.format(self.basefolder, self.basename)
		print("Salvando arquivo {}".format(output))
		with open(output, 'w') as outfile:  
			content = self.to_json()
			outfile.write(content)
