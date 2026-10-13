import {CanActivateFn, Router, Routes} from '@angular/router';
import {inject} from '@angular/core';
import {catchError, map, of} from 'rxjs';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {CrumbTypeEnum} from '@common/layout/breadcrumbs/breadcrumbs.component';
import {provideEffects} from '@ngrx/effects';
import {ReportsEffects} from '@common/reports/reports.effects';
import {commonProjectsProviders} from '@common/projects/common-projects.providers';

const ownProfileGuard: CanActivateFn = () => {
  const router = inject(Router);
  return inject(ApiIamService).me().pipe(
    map(({user}) => router.createUrlTree(['/user', user.username])),
    catchError(() => of(router.parseUrl('/home')))
  );
};

const legacyProfileGuard: CanActivateFn = route => {
  const router = inject(Router);
  return inject(ApiIamService).getProfileById(route.params['userId']).pipe(
    map(({user}) => router.createUrlTree(['/user', user.username])),
    catchError(() => of(router.parseUrl('/404')))
  );
};

export const routes: Routes = [{
  path: '',
  providers: [provideEffects([ReportsEffects]), ...commonProjectsProviders],
  children: [
    {path: '', pathMatch: 'full', children: [], canActivate: [ownProfileGuard]},
    {path: ':username', loadComponent: () => import('./profiles.component').then(m => m.ProfilesComponent),
      data: {staticBreadcrumb: [[{name: 'PROFILE', type: CrumbTypeEnum.Feature}]]}}
  ]
}];

export const legacyRoutes: Routes = [
  {path: '', pathMatch: 'full', redirectTo: '/user'},
  {path: ':userId', children: [], canActivate: [legacyProfileGuard]}
];
