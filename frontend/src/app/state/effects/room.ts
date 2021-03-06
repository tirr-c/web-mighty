import { Injectable } from '@angular/core';
import { Http, Headers } from '@angular/http';
import { Store, Action } from '@ngrx/store';
import { Effect, Actions } from '@ngrx/effects';

import 'rxjs/add/operator/map';
import 'rxjs/add/operator/mergeMap';
import 'rxjs/add/operator/catch';
import 'rxjs/add/operator/first';
import { Observable } from 'rxjs/Observable';
import 'rxjs/add/observable/of';
import 'rxjs/add/observable/never';
import 'rxjs/add/observable/throw';

import { Room } from '../../room';
import { State } from '../reducer';
import * as RoomActions from '../actions/room';
import * as RouterActions from '../actions/router';
import * as GameActions from '../actions/game';

@Injectable()
export class RoomEffects {
  private static getRoomsFailedMessage =
    'Internal server error.';

  private static createRoomFailedMessage =
    'Creating new game failed.';

  private static jsonHeaders = new Headers({
    'Content-Type': 'application/json',
  });

  // TODO: implement effects
  @Effect()
  getRooms$: Observable<Action> =
    this.actions$.ofType(RoomActions.GET_ROOMS_START)
    .map((action: RoomActions.GetRooms.Start) => action.payload)
    .mergeMap(params =>
      this.http.get('/api/room/',
        JSON.stringify(params)
      ).mergeMap((response): Observable<Action> => {
        if (!response.ok) {
          return Observable.throw(response);
        }
        const roomList: Room[] = response.json().rooms;
        return Observable.of(new RoomActions.GetRooms.Done(roomList));
      }).catch((response): Observable<Action> => {
        if (response.status === 500) {
          return Observable.of(
            new RoomActions.GetRooms.Failed(RoomEffects.getRoomsFailedMessage)
          );
        }
        return Observable.of(
          new RoomActions.GetRooms.Failed('Unknown error.')
        );
      })
    );

  @Effect()
  createRoom$: Observable<Action> =
    this.actions$.ofType(RoomActions.CREATE_ROOM_START)
    .map((action: RoomActions.CreateRoom.Start) => action.payload)
    .mergeMap(params =>
      this.http.post('/api/room/',
        JSON.stringify(params),
        { headers: RoomEffects.jsonHeaders }
      ).mergeMap((response): Observable<Action> => {
        if (!response.ok) {
          return Observable.throw(response);
        }
        const room: Room = response.json();
        return Observable.of(
          new GameActions.JoinRoom({
            roomId: room.room_id,
            password: params.password,
          }) as Action,
          new RoomActions.CreateRoom.Done(room) as Action
        );
      }).catch((response): Observable<Action> =>
        Observable.of(
          new RoomActions.CreateRoom.Failed(RoomEffects.createRoomFailedMessage)
        )
      )
    );

  constructor(
    private actions$: Actions,
    private http: Http,
    private store: Store<State>,
  ) {}
}
