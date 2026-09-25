import {inject} from '@angular/core';
import {CanActivateFn, Router} from '@angular/router';
import {Store} from '@ngrx/store';
import {catchError, filter, map, switchMap, take} from 'rxjs/operators';
import {selectCurrentUser} from '@common/core/reducers/users-reducer';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {of} from 'rxjs';

export const iamAdminGuard: CanActivateFn = () => {
  const store = inject(Store);
  const router = inject(Router);
  const iam = inject(ApiIamService);
  return store.select(selectCurrentUser).pipe(
    filter(Boolean),
    take(1),
    switchMap(user => user.role === 'admin' ? iam.status().pipe(
      map(status => status.enabled ? true : router.createUrlTree(['/settings/profile'])),
      catchError(() => of(router.createUrlTree(['/settings/profile'])))
    ) : of(router.createUrlTree(['/settings/profile'])))
  );
};
