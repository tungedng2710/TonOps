import {inject, Injectable} from '@angular/core';
import {Store} from '@ngrx/store';
import {addMessage} from '@common/core/actions/layout.actions';
import {Error as ApiError, ErrorService} from '@common/shared/services/error.service';

@Injectable({providedIn: 'root'})
export class IamNotificationsService {
  private store = inject(Store);
  private errorService = inject(ErrorService);

  error(summary: string, response?: {error?: ApiError}) {
    const detail = response?.error ? this.errorService.getErrorMsg(response.error) : '';
    this.store.dispatch(addMessage('error', detail ? `${summary}: ${detail}` : summary));
  }
}
