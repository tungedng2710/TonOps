import {TestBed} from '@angular/core/testing';
import {Store} from '@ngrx/store';
import {ErrorService} from '@common/shared/services/error.service';
import {IamNotificationsService} from './iam-notifications.service';

describe('IamNotificationsService', () => {
  it('shows the API validation message through the native app notifier', () => {
    const store = jasmine.createSpyObj<Store>('Store', ['dispatch']);
    const errors = jasmine.createSpyObj<ErrorService>('ErrorService', ['getErrorMsg']);
    errors.getErrorMsg.and.returnValue('Username already exists');
    TestBed.configureTestingModule({providers: [
      IamNotificationsService,
      {provide: Store, useValue: store},
      {provide: ErrorService, useValue: errors}
    ]});

    TestBed.inject(IamNotificationsService).error('Unable to save user', {
      error: {meta: {result_code: 400, result_subcode: 0, result_msg: 'duplicate'}, data: {}}
    });

    expect(store.dispatch).toHaveBeenCalledWith(jasmine.objectContaining({
      severity: 'error', msg: 'Unable to save user: Username already exists'
    }));
  });
});
