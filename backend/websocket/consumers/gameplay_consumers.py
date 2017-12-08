from channels import Channel, Group
from .card import shuffled_card, hand_score, is_valid_card, card_in, is_same_card
from .card import is_mighty, is_joker_call, card_index, win_card, suit_count
from .card import filter_score_card
from .consumer_utils import event, reply_error, response
from django.core.cache import cache
from .state import RoomState
from random import shuffle


def gameplay_start_consumer(message):
    data = message.content
    room_id = data['room_id']

    room = cache.get('room:' + room_id)
    player_number = room['options']['player_number']

    cards = shuffled_card()

    # dealing
    if player_number == 5:
        cards_per_person = 10

    elif player_number == 6:
        cards_per_person = 8

    else:
        # this is unexpected exception, but can be validated before
        return

    for i in range(player_number):
        dealed_card = cards[:cards_per_person]
        room['players'][i]['cards'] = dealed_card

        reply_channel = Channel(room['players'][i]['reply'])
        data = {
            'cards': dealed_card,
        }
        reply_channel.send(event('gameplay-deal', data))

        del cards[:cards_per_person]

    room['game']['floor_cards'] = cards
    room['game']['state'] = RoomState.BIDDING
    room['game']['player_number'] = room['options']['player_number']

    cache.set('room:' + room_id, room)

    # send bidding event
    event_data = {
        'player': {
            'username': room['players'][0]['username'],
        }
    }
    Group(room_id).send(event('gameplay-bidding', event_data))


def gameplay_bid_consumer(message):
    data = message.content
    username = data['username']
    nonce = data['nonce']
    reply_channel = Channel(data['reply'])
    room_id = cache.get('player-room:' + username)

    if room_id is None:
        reply_channel.send(reply_error(
            'You are not in room',
            nonce=nonce,
            type='gameplay-bid',
        ))
        return

    score = data.get('score', None)
    giruda = data.get('giruda', None)
    try_bid = data.get('bid', None)

    if not all([score, giruda, try_bid]):
        reply_channel.send(reply_error(
            'Invalid request',
            nonce=nonce,
            type='gameplay-bid',
        ))
        return

    room = cache.get('room:' + room_id)
    turn = room['game']['turn']

    player_number = room['game']['player_number']

    if room['game']['state'] is not RoomState.BIDDING:
        reply_channel.send(reply_error(
            'Invalid request',
            nonce=nonce,
            type='gameplay-bid',
        ))
        return

    if room['players'][turn]['username'] != username:
        reply_channel.send(reply_error(
            'Not your turn',
            nonce=nonce,
            type='gameplay-bid',
        ))
        return

    if not try_bid:
        room['players'][turn]['bid'] = 2

        bidder_count = 0
        bidder = ''
        bidder_turn = 0
        bidder_reply = ''
        for i, player in enumerate(room['players']):
            if player['bid'] == 1:
                bidder_count = bidder_count + 1
                bidder = player['username']
                bidder_turn = i
                bidder_reply = player['reply']

        if bidder_count == 1:
            turn = bidder_turn
            reply_channel = Channel(bidder_reply)
            room['game']['president'] = bidder
            room['game']['current_bid']['bidder'] = bidder
            room['game']['bid_score'] = room['game']['current_bid']['score']
            room['game']['giruda'] = room['game']['current_bid']['giruda']

            players = room['players'][turn:] + room['players'][:turn]
            room['players'] = players
            room['game']['turn'] = 0

            event_data = {
                'player': bidder,
                'score': room['game']['bid_score'],
                'giruda': room['game']['giruda'],
            }

            Group(room_id).send(event(
                'gameplay-president-elected',
                event_data,
            ))

            if player_number == 5:
                room['game']['state'] = RoomState.FRIEND_SELECTING

                event_data = {
                    'floor_cards': room['game']['floor_cards'],
                }
                reply_channel.send(event(
                    'gameplay-floor-cards',
                    event_data,
                ))
                event_data = {
                    'player': bidder,
                }
                Group(room_id).send(event(
                    'gameplay-friend-selecting',
                    event_data,
                ))
            elif player_number == 6:
                room['game']['state'] = RoomState.KILL_SELECTING
                event_data = {
                    'player': bidder,
                }
                Group(room_id).send(event(
                    'gameplay-killing',
                    event_data,
                ))

            cache.set('room:' + room_id, room)
            return

        for i in range(turn + 1, turn + player_number):
            j = i % player_number
            player = room['players'][j]
            if player['bid'] != 2:
                room['game']['turn'] = i
                turn = i
                break

        room['game']['turn'] = turn
        cache.set('room:' + room_id, room)

        reply_channel.send(response(
            {},
            nonce=nonce,
        ))
        event_data = {
            'player': username,
            'bid': False,
        }
        Group(room_id).send(event(
            'gameplay-bid',
            event_data,
        ))
        event_data = {
            'player': room['players'][turn]['username'],
        }
        Group(room_id).send(event(
            'gameplay-bidding',
            event_data,
        ))
        return

    if giruda not in 'SDCHN':
        reply_channel.send(reply_error(
            'Invalid giruda',
            nonce=nonce,
            type='gameplay-bid',
        ))
        return

    if player_number == 5:
        miminum_bid = 13
    elif player_number == 6:
        miminum_bid = 14
    else:
        miminum_bid = 13

    tuned_score = score if giruda != 'N' else score - 1

    if tuned_score < miminum_bid or score > 20:
        reply_channel.send(reply_error(
            'Invalid score',
            nonce=nonce,
            type='gameplay-bid',
        ))
        return

    current_bid = room['game']['current_bid']
    tuned_current_bid = current_bid['score'] if current_bid['giruda'] != 'N' else current_bid['score'] - 1

    if tuned_score < miminum_bid or tuned_current_bid >= tuned_score:
        reply_channel.send(reply_error(
            'Not enough score',
            nonce=nonce,
            type='gameplay-bid',
        ))
        return

    room['game']['current_bid']['bidder'] = username
    room['game']['current_bid']['score'] = score
    room['game']['current_bid']['giruda'] = giruda
    room['player'][turn]['bid'] = 1

    for i in range(turn + 1, turn + player_number):
        j = i % player_number
        player = room['players'][j]
        if player['bid'] != 2:
            room['game']['turn'] = i
            turn = i
            break

    room['game']['turn'] = turn

    cache.set('room:' + room_id, room)

    reply_channel.send(response(
        {},
        nonce=nonce,
    ))
    event_data = {
        'player': username,
        'bid': True,
        'score': score,
        'giruda': giruda,
    }
    Group(room_id).send(event(
        'gameplay-bid',
        event_data,
    ))
    event_data = {
        'player': room['players'][turn]['username'],
    }
    Group(room_id).send(event(
        'gameplay-bidding',
        event_data,
    ))


def gameplay_deal_miss_consumer(message):
    data = message.content
    username = data['username']
    nonce = data['nonce']
    reply_channel = Channel(data['reply'])
    room_id = cache.get('player-room:' + username)

    if room_id is None:
        reply_channel.send(reply_error(
            'You are not in room',
            nonce=nonce,
            type='gameplay-bid',
        ))
        return

    room = cache.get('room:' + room_id)

    if room['game']['state'].value > RoomState.FRIEND_SELECTING.value:
        reply_channel.send(reply_error(
            'Invalid request',
            nonce=nonce,
            type='gameplay-bid',
        ))
        return

    cards = []

    for player in room['players']:
        if player['username'] == username:
            cards = player['cards']
            score = hand_score(cards)
            break

    if score > 0:
        reply_channel.send(reply_error(
            'Invalid score',
            nonce=nonce,
            type='gameplay-bid',
        ))
        return

    event_data = {
        'player': username,
        'cards': cards,
    }

    Group(room_id).send(event(
        'gameplay-deal-miss',
        event_data,
    ))
    Channel('room-reset').send({'room_id': room_id})


def gameplay_kill_consumer(message):
    data = message.content
    username = data['username']
    nonce = data['nonce']
    reply_channel = Channel(data['reply'])
    room_id = cache.get('player-room:' + username)

    if room_id is None:
        reply_channel.send(reply_error(
            'You are not in room',
            nonce=nonce,
            type='gameplay-kill',
        ))
        return

    room = cache.get('room:' + room_id)

    if room['game']['state'] is not RoomState.KILL_SELECTING:
        reply_channel.send(reply_error(
            'Invalid request',
            nonce=nonce,
            type='gameplay-kill',
        ))
        return

    if room['game']['president'] != username:
        reply_channel.send(reply_error(
            'You are not a president',
            nonce=nonce,
            type='gameplay-kill',
        ))
        return

    kill_card = data.get('card', None)

    if kill_card is None:
        reply_channel.send(reply_error(
            'No card',
            nonce=nonce,
            type='gameplay-kill',
        ))
        return

    if not is_valid_card(kill_card):
        reply_channel.send(reply_error(
            'Invalid card type',
            nonce=nonce,
            type='gameplay-kill',
        ))
        return

    floor_cards = room['game']['floor_cards']
    for i, player in enumerate(room['players']):
        if player['username'] == username:
            if card_in(kill_card, player['cards']):
                reply_channel.send(reply_error(
                    'You cannot kill yourself',
                    nonce=nonce,
                    type='gameplay-kill',
                ))
                return

            if card_in(kill_card, floor_cards):
                # President kill
                room['game']['killed_player'] = player
                killed_card = room['players'][i]['cards']
                del room['players'][i]

                event_data = {
                    'player': player['username'],
                    'card': kill_card,
                }

                Group(room_id).send(event(
                    'gameplay-kill',
                    event_data,
                ))

                shuffle(killed_card)
                for p in room['players']:
                    event_data = {
                        'cards': killed_card[:2],
                    }
                    p['cards'] += killed_card[:2]
                    Channel(p['reply']).send(event(
                        'gameplay-kill-deal',
                        event_data,
                    ))
                    del killed_card[:2]

                room['game']['state'] = RoomState.BIDDING
                room['game']['turn'] = 0
                room['game']['player_number'] = 5
                room['game']['president'] = ''
                room['game']['bid_score'] = 0
                room['game']['giruda'] = ''
                room['game']['current_bid'] = {
                    'bidder': '',
                    'score': 0,
                    'giruda': '',
                }

                cache.set('room:' + room_id, room)
                # send bidding event
                event_data = {
                    'player': {
                        'username': room['players'][0]['username'],
                    }
                }
                Group(room_id).send(event('gameplay-bidding', event_data))
                return

        elif card_in(kill_card, player['cards']):
            room['game']['killed_player'] = player
            killed_card = room['players'][i]['cards'] + floor_cards
            del room['players'][i]

            event_data = {
                'player': player['username'],
                'card': kill_card,
            }

            Group(room_id).send(event(
                'gameplay-kill',
                event_data,
            ))

            shuffle(killed_card)
            for i, p in enumerate(room['players']):
                if p['username'] != username:
                    event_data = {
                        'cards': killed_card[:2],
                    }
                    room['players'][i]['cards'] += killed_card[:2]
                    del killed_card[:2]
                else:
                    event_data = {
                        'cards': killed_card[:5],
                    }
                    room['players'][i]['cards'] += killed_card[:5]
                    del killed_card[:5]
                Channel(p['reply']).send(event(
                    'gameplay-kill-deal',
                    event_data,
                ))

            room['game']['state'] = RoomState.FRIEND_SELECTING
            room['game']['player_number'] = 5
            room['game']['turn'] = 0
            cache.set('room:' + room_id, room)
            event_data = {
                'player': username,
            }
            Group(room_id).send(event(
                'gameplay-friend-selecting',
                event_data,
            ))


def gameplay_friend_select_consumer(message):
    data = message.content
    username = data['username']
    nonce = data['nonce']
    reply_channel = Channel(data['reply'])
    room_id = cache.get('player-room:' + username)

    if room_id is None:
        reply_channel.send(reply_error(
            'You are not in room',
            nonce=nonce,
            type='gameplay-friend-select',
        ))
        return

    room = cache.get('room:' + room_id)

    if room['game']['state'] is not RoomState.FRIEND_SELECTING:
        reply_channel.send(reply_error(
            'Invalid request',
            nonce=nonce,
            type='gameplay-friend-select',
        ))
        return

    if room['game']['president'] != username:
        reply_channel.send(reply_error(
            'You are not president',
            nonce=nonce,
            type='gameplay-friend-select',
        ))
        return

    floor_cards = data.get('floor-cards', None)

    if floor_cards is None:
        reply_channel.send(reply_error(
            'Invalid floor cards',
            nonce=nonce,
            type='gameplay-friend-select',
        ))
        return

    player_card = []
    room['floor_cards'] = []
    for p in room['players']:
        if p['username'] == username:
            player_card = p['cards']
            break

    for c in floor_cards:
        ci = card_index(c, player_card)
        if ci == -1:
            reply_channel.send(reply_error(
                'Invalid floor cards',
                nonce=nonce,
                type='gameplay-friend-select',
            ))
            return
        room['floor_cards'].append(c)
        del player_card[ci]

    type = data.get('type', None)

    if type is None or type not in ['no', 'card', 'player', 'turn']:
        reply_channel.send(reply_error(
            'Invalid friend type',
            nonce=nonce,
            type='gameplay-friend-select',
        ))
        return

    event_data = {
        'type': type,
    }

    if type == 'no':
        pass

    elif type == 'card':
        card = data.get('card', None)
        if card is None or not is_valid_card(card):
            reply_channel.send(reply_error(
                'Invalid card',
                nonce=nonce,
                type='gameplay-friend-select',
            ))
            return

        if card_in(card, player_card):
            reply_channel.send(reply_error(
                'You cannot select your card',
                nonce=nonce,
                type='gameplay-friend-select',
            ))
            return

        room['game']['friend_selection']['type'] = 'card'
        room['game']['friend_selection']['card'] = card
        event_data['card'] = card

    elif type == 'player':
        p = data.get('player', None)
        if p is None or not isinstance(p, str):
            reply_channel.send(reply_error(
                'Invalid player',
                nonce=nonce,
                type='gameplay-friend-select',
            ))
            return

        found = False
        for player in room['players']:
            if player['username'] == p:
                found = True
                room['game']['friend_selection']['type'] = 'player'
                room['game']['friend_selection']['player'] = p
                event_data['player'] = p
                break

        if not found:
            reply_channel.send(reply_error(
                'Invalid player',
                nonce=nonce,
                type='gameplay-friend-select',
            ))
            return

    elif type == 'turn':
        t = data.get('turn', None)
        if t is None or not isinstance(t, int) or t < 1 or t > 10:
            reply_channel.send(reply_error(
                'Invalid turn',
                nonce=nonce,
                type='gameplay-friend-select',
            ))
            return

        room['game']['friend_selection']['type'] = 'turn'
        room['game']['friend_selection']['turn'] = t
        event_data['turn'] = t

    change_bid = data.get('change-bid', None)

    if change_bid is not None and isinstance(change_bid, dict):
        bid = change_bid.get('bid', None)
        giruda = change_bid.get('giruda', None)
        if bid is None or giruda is None:
            reply_channel.send(reply_error(
                'Invalid bid or giruda change',
                nonce=nonce,
                type='gameplay-friend-select',
            ))
            return
        current_bid = room['game']['bid_score']
        current_giruda = room['game']['giruda']
        change_score = bid if giruda != 'N' else bid - 1
        current_score = current_bid if current_giruda != 'N' else current_bid - 1

        if change_score < current_score + 2:
            reply_channel.send(reply_error(
                'Not enough bid',
                nonce=nonce,
                type='gameplay-friend-select',
            ))
            return

        room['game']['bid_score'] = bid
        room['game']['giruda'] = giruda

    room['game']['state'] = RoomState.PLAYING
    room['game']['turn'] = 0
    room['game']['round'] = 1

    reply_channel.send(response(
        {},
        nonce=nonce,
    ))
    Group(room_id).send(event(
        'gameplay-friend-select',
        event_data,
    ))

    if room['game']['friend_selection']['type'] == 'player':
        room['game']['friend'] = room['game']['friend_selection']['player']
        Group(room_id).send(event(
            'gameplay-friend-revealed',
            {'player': room['game']['friend']},
        ))

    cache.set('room:' + room_id, room)

    event_data = {
        'player': username,
    }

    Group(room_id).send(event(
        'gameplay-turn',
        event_data,
    ))


def gameplay_play_consumer(message):
    data = message.content
    username = data['username']
    nonce = data['nonce']
    reply_channel = Channel(data['reply'])
    room_id = cache.get('player-room:' + username)

    if room_id is None:
        reply_channel.send(reply_error(
            'You are not in room',
            nonce=nonce,
            type='gameplay-play',
        ))
        return

    room = cache.get('room:' + room_id)

    if room['game']['state'] != RoomState.PLAYING:
        reply_channel.send(reply_error(
            'Invalid request',
            nonce=nonce,
            type='gameplay-play',
        ))
        return

    turn = room['game']['turn']

    if room['players'][turn]['username'] != username:
        reply_channel.send(reply_error(
            'Not your turn',
            nonce=nonce,
            type='gameplay-play',
        ))
        return

    # card validation from here

    player_card = room['players'][turn]['cards']
    card = data.get('card', None)
    round = room['game']['round']

    if card is None or not is_valid_card(card) or not card_in(card, player_card):
        reply_channel.send(reply_error(
            'Invalid card',
            nonce=nonce,
            type='gameplay-play',
        ))
        return

    giruda = room['game']['giruda']
    event_data = {
        'player': username,
        'gan': False,
    }

    is_joker_in = card_in({'rank': 'JK', 'suit': None}, player_card)

    # first round exceptions
    if round == 1:
        if turn == 0 and card['suit'] == giruda:
            giruda_count = suit_count(player_card, giruda)
            if giruda_count != 10 or not (giruda_count == 9 and is_joker_in):
                reply_channel.send(reply_error(
                    'You cannot play giruda at first round, first turn',
                    nonce=nonce,
                    type='gameplay-play',
                ))
                return

    # 9th round joker behaviour
    if is_joker_in and round == 9:
        if card['rank'] != 'JK':
            reply_channel.send(reply_error(
                'You should play joker at 9th turn',
                nonce=nonce,
                type='gameplay-play',
            ))
            return

    if turn == 0:
        # joker
        if card['rank'] == 'JK':
            joker_suit = data.get('joker-suit', None)
            if joker_suit is None:
                reply_channel.send(reply_error(
                    'No joker suit',
                    nonce=nonce,
                    type='gameplay-play',
                ))
                return

            card['suit'] = joker_suit
        # joker-call
        elif is_joker_call(card, giruda):
            joker_call = data.get('joker-call', False)
            if joker_call and round != 1 and round != 10:
                room['game']['joker_call'] = True
            elif joker_call and (round == 1 or round == 10):
                reply_channel.send(reply_error(
                    'You cannot call joker at first or last round',
                    nonce=nonce,
                    type='gameplay-play',
                ))
                return
            event_data['joker-call'] = joker_call
    else:
        joker_call = room['game']['joker_call']
        if joker_call and card_in({'rank': 'JK', 'suit': None}, player_card):
            if card['rank'] != 'JK' and not is_mighty(card, giruda):
                reply_channel.send(reply_error(
                    'You should play joker or mighty when called',
                    nonce=nonce,
                    type='gameplay-play',
                ))
                return

        if card['rank'] != 'JK':
            table_suit = room['game']['table_cards'][0]['suit']
            if table_suit != card['suit']:
                found = False
                for c in player_card:
                    if c['suit'] == table_suit:
                        found = True
                        break
                if found:
                    reply_channel.send(reply_error(
                        'You should play current table suit',
                        nonce=nonce,
                        type='gameplay-play',
                    ))
                    return
                if card['suit'] == giruda:
                    event_data['gan'] = True
        else:
            card['suit'] = None

    # valiation done
    ci = card_index(card, player_card)
    del player_card[ci]

    room['game']['table_cards'].append(card)
    room['players'][turn]['cards'] = player_card

    event_data['card'] = card

    reply_channel.send(response(
        {},
        nonce=nonce,
    ))

    Group(room_id).send(event(
        'gameplay-play',
        event_data,
    ))

    friend_selection = room['game']['friend_selection']
    if friend_selection['type'] == 'card':
        friend_card = friend_selection['card']
        if is_same_card(friend_card, card):
            room['game']['friend'] = username
            event_data = {
                'player': username,
            }
            Group(room_id).send(event(
                'gameplay-friend-revealed',
                event_data,
            ))

    turn += 1

    if turn == room['game']['player_number']:
        # round end
        turn = 0
        win = win_card(
            room['game']['table_cards'],
            room['game']['giruda'],
            room['game']['joker_call'],
            round=round,
        )

        win_player = room['players'][win]['username']
        score_cards = filter_score_card(room['game']['table_cards'])
        room['players'][win]['score'] += len(score_cards)

        f = room['friend_selection']
        if f['type'] == 'turn' and f['turn'] == turn:
            room['game']['friend'] = win_player
            event_data = {
                'player': win_player,
            }
            Group(room_id).send(event(
                'gameplay-friend-revealed',
                event_data,
            ))

        event_data = {
            'player': win_player,
            'score_cards': score_cards,
        }
        Group(room_id).send(event(
            'gameplay-round-end',
            event_data,
        ))
        room['players'] = room['players'][win:] + room['players'][:win]
        room['game']['round'] += 1

    if room['game']['round'] == 10:
        # game end
        pass

    room['game']['table_cards'] = []
    room['game']['turn'] = turn
    room['game']['joker_call'] = False
    room['game']['joker_suit'] = ''

    cache.set('room:' + room_id, room)

    Group(room_id).send(event(
        'gameplay-turn',
        {'player': room['players'][turn]['username']},
    ))
