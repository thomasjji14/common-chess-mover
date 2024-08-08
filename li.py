import requests
import random
import berserk
import time
import chess
import time

class ChessDBCNKibitzer():

    def __init__(self, action = "queryall"):
        self._params = {
            "action" : action
        }

    def getMoves(self, FEN) -> dict:
        self._params["board"] = FEN
        gameURLResponse = requests.get("http://www.chessdb.cn/cdb.php?", params = self._params)
        textResponse = gameURLResponse.text
        return self._parseMoveResponse(textResponse)
    
    def _parseMoveResponse(self, moveText) -> dict:
        parsedDictionary = {}
        lines = moveText.split("|")
        if len(lines) == 0:
            return {}
        for line in lines:
            categorySplits = line.split(",")

            moveText = categorySplits.pop(0)
            if "unknown" in moveText or "mate" in moveText:
                return {}
            uciText = moveText.split(":")[1]
            subDict = {}
            for categorySplit in categorySplits:
                dividedCategoryInfo = categorySplit.split(":")
                categoryName = dividedCategoryInfo[0]
                categoryInfo = dividedCategoryInfo[1]
                subDict[categoryName] = categoryInfo
            
            parsedDictionary[uciText] = subDict
        
        return parsedDictionary

class LichessPlayer():

    # def __init__(self, variant = "standard", speeds = ["bullet", "blitz", "rapid", "classical"], ratings = [1600, 1800, 2000, 2200, 2500], startingMoves = ""):
    def __init__(self, variant = "standard", speeds = ["blitz"], ratings = [2000], startingMoves = ""):
        self._params = {
            "variant": variant,  
            "speeds[]": speeds, 
            "ratings[]" : ratings, 
            "moves" : 999, 
            "recentGames" : 1,
            "play": startingMoves
        }

    def getMove(self, FEN, moves = ""):
        self._params["fen"] = FEN
        self._params["play"] = moves
        print(moves)

        gameURLResponse = requests.get("https://explorer.lichess.ovh/lichess?", params = self._params)

        json_response = gameURLResponse.json()
        moves = json_response['moves']

        moveCumFrequency = {}
        totalGames = 0
        for move in moves:
            moveCount = move['white'] + move['black'] + move["draws"]
            totalGames += moveCount
            moveCumFrequency[move['uci']] = totalGames

        if totalGames == 0:
            print("Out of games.")
            raise ValueError("Done.")

        randomMoveNumber = random.randint(1, totalGames)

        return self._getRandomMove(randomMoveNumber, moveCumFrequency), totalGames

# """
# func findCommonPositions:
#     for a given FEN + moves (i.e. position)
#         if the position has > 1000 positions
#             then mark it to a set of positions, by the fen and a tuple of the moves
#             for each move possible from the position:
#                 call findCOmmonPositons on the FEN + moves + the new move
# """


    def setRatings(self, ratings):
        self._params["ratings[]"] = ratings
    
    def setTimeControl(self, timeControls):
        self._params["speeds[]"] = timeControls

    def _getRandomMove(self, randNum, moveFrequency):
        for key in list(moveFrequency.keys()):
            if randNum <= moveFrequency[key]:
                return key

session = berserk.TokenSession("lip_IcO9LVsQ1JmiBcb93nmW")
client = berserk.Client(session=session)
DEFAULT_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

lp = LichessPlayer()

eventStream = client.bots.stream_incoming_events()
print("Common Mover bot started")
moves = ""

# challenge loops
while True:
    event = next(eventStream)
    print(f"{event=}")
    if event["type"] == "challenge":
        # parse challenge
        game_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" if "initialFen" not in event["challenge"] else event["challenge"]["initialFen"]
        game_id = event["challenge"]["id"]
        
        if event["challenge"]["rated"]: # is true
            client.bots.decline_challenge(game_id)
            continue

        # accept challenge
        gameStreamer = client.bots.stream_game_state(game_id)
        client.challenges.accept(game_id)
        print("-----------------")
        print(f"{game_id}")
        print("-----------------")
        time.sleep(0.1) # ensures that the game starts before listening to it

        chat = lambda msg: client.bots.post_message(game_id, msg)

        # loop that listens to a game
        while True:
            gameEvent = next(gameStreamer)
            print(gameEvent)
            # only continue if the game is active
            if "status" in gameEvent.keys() and gameEvent["status"] != "started":
                break

            # this only happens when the game is first accepted
            if "white" in gameEvent.keys():
                isTurn = ("common_mover" in gameEvent["white"]["id"]) == ("w" in game_fen)


            if gameEvent["type"] in ["gameState", "gameFull"]:
                if isTurn:
                    try:
                        # tries fetching a move from lichess
                        mvs = gameEvent["moves"].replace(" ", ",") if "moves" in gameEvent.keys() else ""
                        move, games = lp.getMove(game_fen, moves = mvs)
                        client.bots.make_move(game_id, move)
                        client.bots.post_message(game_id, "Games remaining: "+str(games)) # needs to be before making a move, can't send message not on turn?
                        moves = (mvs + "," + move).lstrip(",")
                        
                    except Exception as e:
                        print(e)
                        # otherwise resigns and tells the player over chat that they're done
                        client.bots.resign_game(game_id)
                        client.bots.post_message(game_id, "Out of moves; thanks for playing!")
                        break

                isTurn = not isTurn

            elif gameEvent["type"] == "chatLine" and gameEvent["username"] != "Common_Mover":
                text = gameEvent["text"].lower()
                if text == "help":
                    chat("Available Commands: since, until, source, speeds, ratings")
                elif text == "about":
                    chat("Bot made by @Bankerice, tell him I said hi~")
                elif text == "help source":
                    chat("source [master/lichess], gets moves from master databse or lichess's database")
                elif text == "help since":
                    chat("since [YYYY]-[MM], gets move from certain time. Master database ignore months.")
                elif text == "help until":
                    chat("until [YYYY]-[MM], gets move from certain time. Master database ignore months.")
                elif text == "help ratings":
                    chat("ratings [1600, 1800, 2000, 2200, 2500], comma separated ratings")
                elif text == "help speeds":
                    chat("speeds [ultraBullet, bullet, blitz, rapid, classical, correspondence], comma separated")
                elif "eval" in text.lower():
                    # print("recognized eval")
                    board = chess.Board(game_fen)
                    print(f"{moves=}")
                    if len(moves) != 0:
                        for move in moves.split(","):
                            board.push(chess.Move.from_uci(move))
                    db = ChessDBCNKibitzer()

                    evaluation = db.getMoves(board.fen())
                    print(evaluation)
                    if evaluation == {}:
                        chat("No evaluation from DBCN found.")
                    else:
                        chat(" | ".join([f"{board.san(chess.Move.from_uci(move))}: {rank['score']}" for move, rank in evaluation.items()])[:140])