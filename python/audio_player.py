import time
import numpy as np
import pyaudio
import config
import wave
import queue
import os

wave_file = None
loopback_audio_stream = queue.Queue()
audio_file_paths = []
audio_file_index = 0


def scan_audio_files():
	for entry in os.scandir(config.AUDIO_FILE_SCAN_PATH):
		if entry.is_file() and entry.path.endswith('.wav'):
			audio_file_paths.append(entry.path)

	# If only one file, add it twice so the list looping will still work
	if len(audio_file_paths) == 1:
		audio_file_paths.append(audio_file_paths[0])


def need_more_data_callback(in_data, frame_count, time_info, status):
	global wave_file
	global audio_file_index
	ret_status = pyaudio.paComplete

	data = None
	if wave_file:
		data = wave_file.readframes(frame_count)
		if len(data) < frame_count:
			wave_file = None
			# Loop to next audio file
			audio_file_index = (audio_file_index + 1) % len(audio_file_paths)
		else:
			# Pass the data chunks back to visualization via queue
			loopback_audio_stream.put(data)
			# More data to come
			ret_status = pyaudio.paContinue
	return data, ret_status


def start_stream(callback):
	global wave_file

	scan_audio_files()
	p = pyaudio.PyAudio()

	while True:
		playing_audio_file_index = audio_file_index
		audio_file_path = audio_file_paths[audio_file_index]
		wave_file = wave.open(audio_file_path, 'rb')
		assert (wave_file.getframerate() == config.AUDIO_RATE)

		# Creates a Stream to which the wav file is written to.
		# Setting output to "True" makes the sound be "played" rather than recorded
		stream = p.open(format=p.get_format_from_width(wave_file.getsampwidth()),
						channels=wave_file.getnchannels(),
						rate=wave_file.getframerate(),
						output=True,
						stream_callback=need_more_data_callback)

		# Visualize the latest played samples until file changes
		while playing_audio_file_index == audio_file_index:
			# Clear the queue to wait for newest samples
			while not loopback_audio_stream.empty():
				loopback_audio_stream.get(block=False)
			try:
				data = loopback_audio_stream.get(timeout=1)
			except queue.Empty:
				break
			y = np.fromstring(data, dtype=np.int16)
			y = y.astype(np.float32)
			# Small delay before visualization to sync it better
			time.sleep(0.01)
			callback(y)

		# Close the stream
		stream.stop_stream()
		stream.close()

	p.terminate()

