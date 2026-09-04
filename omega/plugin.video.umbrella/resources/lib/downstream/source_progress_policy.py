KEEP_ALIVE_PROPERTY = 'umbrella.window_keep_alive'


def start_source_progress(window, home_window, thread_factory):
	"""Arm the lifecycle before the modal thread can reach a terminal path."""
	home_window.setProperty(KEEP_ALIVE_PROPERTY, 'true')
	thread_factory(target=window.run).start()
	return window


def wait_for_source_progress_release(window, home_window, sleep):
	"""Close a modal after its owner releases it without re-arming the lifecycle."""
	while home_window.getProperty(KEEP_ALIVE_PROPERTY) == 'true':
		sleep(200)
	home_window.clearProperty(KEEP_ALIVE_PROPERTY)
	try:
		window.close()
	except Exception:
		pass
