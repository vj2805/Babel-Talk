import speech_recognition as sr
import pyttsx3 as ts
import deep_translator as dt
import flet as ft
import threading as th
import re

# setting up translator
Translator = dt.GoogleTranslator

# getting support languages


def get_supported_languages():
    return Translator().get_supported_languages(as_dict=True)

# getting voice ids of corresponding language


def get_voice_id(language):
    language = language.upper()
    engine = ts.init()
    for voice in engine.getProperty('voices'):
        if re.search(language, voice.name, re.IGNORECASE):
            return voice.id
    raise UnavailableVoiceException(language)

# exception handling for unavailablevoice


class UnavailableVoiceException(Exception):
    def __init__(self, language):
        super().__init__()
        self.description = f"Voice for {language} is not installed"


class Modulator:
    def __init__(self, language_code, voice_id):
        self.language_code = language_code
        self.voice_id = voice_id
    # recognizing the voice and coverting into text (stt)

    def listen(self):
        recognizer = sr.Recognizer()
        with sr.Microphone() as microphone:
            audio = recognizer.listen(source=microphone)
        try:
            return recognizer.recognize_google(audio,
                                               language=self.language_code)
        except sr.UnknownValueError:
            raise SpeechRecognitionException("Incomprehensible Audio")
        except sr.RequestError:
            raise SpeechRecognitionException("Unrecognizable Audio")
    # Speaks the transulated text in there respective language(tts)

    def speak(self, text):
        engine = ts.init()
        engine.setProperty('voice', self.voice_id)
        engine.setProperty('volume', 1.0)
        engine.setProperty('rate', 150)
        engine.say(text)
        engine.runAndWait()

# exception handling for Speechrecognition


class SpeechRecognitionException(Exception):
    def __init__(self, description):
        super().__init__()
        self.description = description

# UI - Title Bar


class TitleBar(ft.AppBar):
    def __init__(self, title):
        super().__init__(
            title=ft.Text(title),
            center_title=True,
            toolbar_height=70,
            bgcolor=ft.colors.PRIMARY_CONTAINER,
            color=ft.colors.INVERSE_SURFACE
        )

# UI - Prompt


class Prompt(ft.Text):
    EMPTY = 'Click on the MIC to start conversation'

    def __init__(self):
        super().__init__(
            value=self.EMPTY,
            style=ft.TextThemeStyle.TITLE_SMALL,
            color=ft.colors.OUTLINE,
            height=20
        )

    @property
    def text(self):
        return self.value

    @text.setter
    def text(self, value):
        self.value = value
        self.update()

# UI - Coversation container


class Conversation(ft.ListView):
    def __init__(self):
        super().__init__(
            expand=True,
            spacing=5,
            disabled=True,
            padding=ft.padding.symmetric(horizontal=15, vertical=5),
            auto_scroll=True
        )
        self.empty = True

    # clear button used to clear all the chats
    def clear(self):
        self.controls.clear()
        self.update()
        self.empty = True

    # push function used to push to text into the container
    def push(self, text, who) -> None:
        flip = who == 1
        self.controls.append(ft.Row(
            alignment=(ft.MainAxisAlignment.END
                       if flip else ft.MainAxisAlignment.START),
            controls=[
                ft.Container(
                    padding=9,
                    bgcolor=ft.colors.SECONDARY_CONTAINER,
                    border_radius=(ft.border_radius.horizontal(left=8)
                                   if flip else ft.border_radius.horizontal(right=8)),
                    content=(
                        ft.Text(
                            value=text,
                            style=ft.TextThemeStyle.LABEL_LARGE,
                            width=self.page.width/2,

                        )
                    )
                )
            ]
        ))
        self.update()
        self.empty = False

# UI - language selection


class LanguageOption(ft.ListTile):
    CHECK_ICON = ft.Icon(name=ft.icons.CHECK)

    def __init__(self, language, on_click):
        super().__init__(
            title=ft.Text(language.title()),
            data=language,
            on_click=on_click
        )

    @property
    def check(self):
        return self.selected

    @check.setter
    def check(self, value):
        self.trailing = self.CHECK_ICON if value else None
        self.selected = value
        self.update()

# UI - language selection


class LanguageDialog(ft.AlertDialog):
    def __init__(self, languages):
        super().__init__(
            title=ft.Text("Language"),
            modal=True,
            content=ft.ListView(
                controls=[
                    LanguageOption(language, on_click=self.select)
                    for language in languages
                ]
            ),
            actions=[
                ft.OutlinedButton('CANCEL', on_click=self.close),
                ft.FilledButton('OKAY', on_click=self.save)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.selected_language_option = None
        self.on_save = None

    @property
    def height(self):
        return self.content.height

    @height.setter
    def height(self, value):
        self.content.height = value

    @property
    def language(self):
        return self.selected_language_option.data if self.selected_language_option else ''

    @language.setter
    def language(self, value):
        for language_option in self.content.controls:
            if language_option.data == value:
                self.selected_language_option = language_option
                break

    @property
    def show(self):
        return self.open

    @show.setter
    def show(self, value):
        if self.selected_language_option:
            self.selected_language_option.check = value
            if not value:
                self.selected_language_option = None
        self.open = value
        self.update()

    def select(self, e):
        if e.control == self.selected_language_option:
            return
        if self.selected_language_option:
            self.selected_language_option.check = False
        e.control.check = True
        self.selected_language_option = e.control

    def close(self, e):
        self.show = False

    def save(self, e):
        if self.on_save:
            self.on_save(self.language)
        self.close(e)

# UI - Alert Bar used to show the exception/error


class Alert(ft.SnackBar):
    def __init__(self):
        super().__init__(
            content=ft.Text(),
            bgcolor=ft.colors.ERROR
        )

    @property
    def show(self):
        return self.open

    @show.setter
    def show(self, value):
        self.open = value
        self.update()

    @property
    def text(self):
        return self.content.value

    @text.setter
    def text(self, value):
        self.content.value = value
        self.update()

# Translation part


class Task:
    # initialisation
    def __init__(self, prompt, alert, conversation):
        self.prompt = prompt
        self.alert = alert
        self.conversation = conversation
        self.running = False
        self.modulators = None
        self.translators = None
        self.who = 0

    # start the coversation
    def start(self):
        self.running = True
        th.Thread(target=self.task).start()

    # stops the coversation
    def stop(self):
        self.running = False

    # Listening, convertion and translation part
    def task(self):
        while self.running:
            self.prompt.text = f"{'First' if self.who == 0 else 'Second'} Person Say Something"
            try:
                original = self.modulators[self.who].listen()
            except SpeechRecognitionException as e:
                self.alert.text = e.description
                self.alert.show = True
                continue
            if not self.running:
                break
            translated = self.translators[self.who].translate(original)
            self.conversation.push(f"{translated} [{original}]", self.who)
            self.who = 1 - self.who
            if not self.running:
                break
            self.modulators[self.who].speak(translated)
        self.prompt.text = f"Click on the MIC to {'start' if self.conversation.empty else 'continue'} conversation"


# Main
def main(page: ft.Page):
    # getting supported languages
    supported_languages = get_supported_languages()
    # setting theme of the app
    page.dark_theme = ft.Theme(
        font_family='NotoSans', color_scheme_seed=ft.colors.GREEN)
    page.theme_mode = ft.ThemeMode.DARK
    # title text
    page.title = 'BABEL TALK'
    # titleBar
    page.appbar = TitleBar(title=page.title)
    # Language selection
    page.dialog = LanguageDialog(supported_languages)
    page.dialog.height = page.height
    # alert bar
    page.snack_bar = Alert()
    # promt
    prompt = Prompt()
    # coversation container
    conversation = Conversation()
    # calling the Task
    task = Task(prompt, page.snack_bar, conversation)
    selected_languages = ['english', 'tamil']

    # function to clear the conversation
    def clear_conversation(e):
        conversation.clear()
        prompt.text = Prompt.EMPTY
        task.who = 0

    # Function to select language
    def open_language_options(e):
        def on_save(language):
            if not language:
                return
            selected_languages[selected_languages.index(
                e.control.data)] = language
            e.control.text = supported_languages[language].upper()
            e.control.data = language
            e.control.update()

        page.dialog.on_save = on_save
        page.dialog.language = e.control.data
        page.dialog.show = True

    # Executing the coversation
    def execute(e):
        if task.running:
            task.stop()
            e.control.icon = ft.icons.MIC_ROUNDED
            e.control.update()
            return
        try:
            task.modulators = (
                Modulator(language_code=supported_languages[selected_languages[0]],
                          voice_id=get_voice_id(selected_languages[0])),
                Modulator(language_code=supported_languages[selected_languages[1]],
                          voice_id=get_voice_id(selected_languages[1]))
            )
        except UnavailableVoiceException as ex:
            page.snack_bar.text = ex.description
            page.snack_bar.show = True
            return
        task.translators = (
            Translator(source=supported_languages[selected_languages[0]],
                       target=supported_languages[selected_languages[1]]),
            Translator(source=supported_languages[selected_languages[1]],
                       target=supported_languages[selected_languages[0]])
        )
        task.start()
        e.control.icon = ft.icons.STOP
        e.control.update()
    # UI
    page.add(
        ft.Column(
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    # promt placement
                    controls=[
                        prompt,
                        ft.TextButton(
                            text='Clear',
                            on_click=clear_conversation
                        )
                    ]
                ),
                # converstaion placement
                conversation,
                # Button placement
                ft.Container(
                    padding=ft.padding.symmetric(vertical=30),
                    content=(
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=30,
                            controls=[
                                ft.FilledButton(
                                    text=supported_languages[selected_languages[0]].upper(
                                    ),
                                    data=selected_languages[0],
                                    on_click=open_language_options
                                ),
                                ft.IconButton(
                                    icon=ft.icons.MIC,
                                    icon_size=60,
                                    icon_color=ft.colors.INVERSE_PRIMARY,
                                    bgcolor=ft.colors.PRIMARY,
                                    on_click=execute
                                ),
                                ft.FilledButton(
                                    text=supported_languages[selected_languages[1]].upper(
                                    ),
                                    data=selected_languages[1],
                                    on_click=open_language_options

                                )
                            ]
                        )
                    )
                )
            ]
        )
    )


if __name__ == '__main__':
    ft.app(target=main)
