from resources.lib.downstream.source_progress_policy import (
	KEEP_ALIVE_PROPERTY,
	start_source_progress,
	wait_for_source_progress_release,
)


class HomeWindow:
	def __init__(self):
		self.properties = {}
		self.events = []

	def setProperty(self, key, value):
		self.properties[key] = value
		self.events.append(('set', key, value))

	def getProperty(self, key):
		return self.properties.get(key, '')

	def clearProperty(self, key):
		self.properties.pop(key, None)
		self.events.append(('clear', key))


class Window:
	def __init__(self):
		self.ran = False
		self.closed = False

	def run(self):
		self.ran = True

	def close(self):
		self.closed = True


class InspectingThread:
	def __init__(self, target, home_window):
		self.target = target
		self.home_window = home_window

	def start(self):
		assert self.home_window.getProperty(KEEP_ALIVE_PROPERTY) == 'true'
		self.target()


def test_progress_lifecycle_is_armed_before_modal_thread_starts():
	home_window = HomeWindow()
	window = Window()

	result = start_source_progress(
		window,
		home_window,
		lambda target: InspectingThread(target, home_window),
	)

	assert result is window
	assert window.ran is True
	assert home_window.getProperty(KEEP_ALIVE_PROPERTY) == 'true'


def test_monitor_does_not_resurrect_lifecycle_after_terminal_release():
	home_window = HomeWindow()
	window = Window()
	home_window.clearProperty(KEEP_ALIVE_PROPERTY)

	wait_for_source_progress_release(window, home_window, lambda _milliseconds: None)

	assert window.closed is True
	assert home_window.getProperty(KEEP_ALIVE_PROPERTY) == ''
	assert not any(event[0] == 'set' for event in home_window.events)
