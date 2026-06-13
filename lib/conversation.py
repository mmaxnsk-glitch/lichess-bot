"""Allows lichess-bot to send messages to the chat."""
import logging
import chess
from random import randint
import random
from lib import model
from lib.engine_wrapper import EngineWrapper
from lib.lichess import Lichess
from lib.lichess_types import GameEventType
from collections.abc import Sequence
from lib.timer import seconds
MULTIPROCESSING_LIST_TYPE = Sequence[model.Challenge]

logger = logging.getLogger(__name__)


class ChatLine:
    """Information about the message."""

    def __init__(self, message_info: GameEventType) -> None:
        """Information about the message."""
        self.room = message_info["room"]
        """Whether the message was sent in the chat room or in the spectator room."""
        self.username = message_info["username"]
        """The username of the account that sent the message."""
        self.text = message_info["text"]
        """The message sent."""


class Conversation:
    """Enables the bot to communicate with its opponent and the spectators."""

    def __init__(self, game: model.Game, engine: EngineWrapper, li: Lichess, version: str,
                 challenge_queue: MULTIPROCESSING_LIST_TYPE) -> None:
        """
        Communication between lichess-bot and the game chats.

        :param game: The game that the bot will send messages to.
        :param engine: The engine playing the game.
        :param li: A class that is used for communication with lichess.
        :param version: The lichess-bot version.
        :param challenge_queue: The active challenges the bot has.
        """
        self.game = game
        self.engine = engine
        self.li = li
        self.version = version
        self.challengers = challenge_queue
        self.messages: list[ChatLine] = []

    command_prefix = "!"

    def react(self, line: ChatLine) -> None:
        """
        React to a received message.

        :param line: Information about the message.
        """
        self.messages.append(line)
        logger.info(f"*** {self.game.url()} [{line.room}] {line.username}: {line.text}")
        if line.text[0] == self.command_prefix:
            self.command(line, line.text[1:].lower())

    def command(self, line: ChatLine, cmd: str) -> None:
        """
        Reacts to the specific commands in the chat.

        :param line: Information about the message.
        :param cmd: The command to react to.
        """
        from_self = line.username == self.game.username
        is_eval = cmd.startswith("eval")
        if cmd in ("commands", "help"):
            self.send_reply(line,
                            "Supported commands: !wait (wait a minute for my first move), !name, "
                            "!eval, !queue, !engine, !CPU, !info, !info2 (you will find many interesting features)")
        elif cmd == "wait" and self.game.is_abortable():
            self.game.ping(seconds(60), seconds(120), seconds(120))
            self.send_reply(line, "Waiting 60 seconds...")
        elif cmd == "name":
            name = self.game.me.name
            self.send_reply(line, f"{name} running {self.engine.name()} (lichess-bot v{self.version})")
        elif is_eval and (from_self or line.room == "spectator"):
            stats = self.engine.get_stats(for_chat=True)
            self.send_reply(line, ", ".join(stats))
        elif is_eval:
            self.send_reply(line, "I don't tell that to my opponent, sorry.")
        elif cmd == "queue":
            if self.challengers:
                challengers = ", ".join([f"@{challenger.challenger.name}" for challenger in reversed(self.challengers)])
                self.send_reply(line, f"Challenge queue: {challengers}")
            else:
                self.send_reply(line, "No challenges queued.")
        elif cmd == "engine":
            self.send_reply(line, "This engine is a symbiosis of Stockfish and Leela, as well as a bit of Dragon.")
        elif cmd == "CPU":
            self.send_reply(line, "something between linux and windows")
        elif cmd == "info":
            self.send_reply(line, "My creator @hihihihahahaha My club  lichess.org /team /zipfile_chess_bot."
                                  " PLZ join my club!!!")
        elif cmd == "info1":
            self.send_reply(line, "I can answer the question (!question?), !calc")
        elif "?" in cmd:
            otvet = ["Yes", "No", "Don't know"]
            x = randint(0, 2)
            self.send_reply(line, f"{otvet[x]}")
        elif "calc" in cmd:
            try:
                # Get the entire string after !calc
                expression_str = line.text[5:].strip()  # remove "!calc"

                # Split the expression into parts
                parts = expression_str.split()

                # Check that we have 3 parts: x operator y
                if len(parts) != 3:
                    self.send_reply(line, "Usage: !calc number operator number Example: !calc 6 + 7")
                    return

                x_str, operator, y_str = parts

                # Convert strings to numbers (support complex numbers)
                try:
                    # Try to convert to complex numbers
                    x = complex(x_str.replace('i', 'j').replace(',', '.'))
                    y = complex(y_str.replace('i', 'j').replace(',', '.'))
                except ValueError:
                    # If that fails, try as real numbers
                    try:
                        x = float(x_str.replace(',', '.'))
                        y = float(y_str.replace(',', '.'))
                    except ValueError:
                        self.send_reply(line, "Error: invalid number format")
                        return

                # Perform the operation based on the operator
                result = None
                if operator == '+':
                    result = x + y
                elif operator == '-':
                    result = x - y
                elif operator == '*':
                    result = x * y
                elif operator == '/':
                    if y == 0:
                        self.send_reply(line, "Error: division by zero")
                        return
                    result = x / y
                elif operator == '**' or operator == '^':
                    result = x ** y
                elif operator == '%':
                    if isinstance(x, complex) or isinstance(y, complex):
                        self.send_reply(line, "Error: % operation not supported for complex numbers")
                        return
                    result = x % y
                elif operator == '//':
                    if isinstance(x, complex) or isinstance(y, complex):
                        self.send_reply(line, "Error: integer division not supported for complex numbers")
                        return
                    result = x // y
                else:
                    self.send_reply(line, f"Unknown operator: {operator} Available: + - * / ** ^ % //")
                    return

                # Format the result
                if isinstance(result, complex):
                    # Format complex numbers nicely
                    real = result.real
                    imag = result.imag
                    if real == 0 and imag == 0:
                        response = "0"
                    elif real == 0:
                        response = f"{imag}i"
                    elif imag == 0:
                        response = f"{real}"
                    else:
                        sign = '+' if imag > 0 else ''
                        response = f"{real}{sign}{imag}i"
                else:
                    # For real numbers
                    response = str(result)

                self.send_reply(line, f"{x} {operator} {y} = {response}")

            except Exception as e:
                self.send_reply(line, f"Error: {str(e)}")


        elif cmd.startswith("skill") and line.room == "player":
            parts = cmd.split()
            if len(parts) == 2:
                try:
                    level = int(parts[1])
                    if 0 <= level <= 20:
                        self.engine.set_skill_level(level)
                        self.send_reply(line, f"Skill level set to {level}")
                    else:
                        self.send_reply(line, "Skill level must be 0-20")
                except ValueError:
                    self.send_reply(line, "Usage: !skill <0-20>")

        elif cmd.startswith("hint"):
            # Check if it's a rated game
            if self.game.rated:
                self.send_reply(line,
                                "Hints only in casual games. You wouldn't want to be suspected of cheating, "
                                "would you? ;)")
                return

            try:
                board = self.game.board
                # Quick analysis (0.3 seconds is enough for a hint)
                result = self.engine.analyse(board, chess.engine.Limit(time=0.3))

                if "pv" in result and result["pv"]:
                    move = result["pv"][0]
                    san_move = board.san(move)
                    self.send_reply(line, f"Hint: {san_move}")
                else:
                    self.send_reply(line, "No hint available")

            except Exception as e:
                self.send_reply(line, f"Error getting hint: {str(e)}")
                logger.error(f"Hint error: {e}")

    def send_reply(self, line: ChatLine, reply: str) -> None:
        """
        Send the reply to the chat.

        :param line: Information about the original message that we reply to.
        :param reply: The reply to send.
        """
        logger.info(f"*** {self.game.url()} [{line.room}] {self.game.username}: {reply}")
        self.li.chat(self.game.id, line.room, reply)

    def send_message(self, room: str, message: str) -> None:
        """Send the message to the chat."""
        if message:
            self.send_reply(ChatLine({"room": room, "username": "", "text": ""}), message)
