import {Routes} from '@angular/router';
import {provideEffects} from '@ngrx/effects';
import {ReportsEffects} from '@common/reports/reports.effects';
import {commonProjectsProviders} from '@common/projects/common-projects.providers';

export const routes: Routes = [{
  path: '',
  providers: [provideEffects([ReportsEffects]), ...commonProjectsProviders],
  children: [
    {path: '', loadComponent: () => import('./profiles.component').then(m => m.ProfilesComponent)},
    {path: ':userId', loadComponent: () => import('./profiles.component').then(m => m.ProfilesComponent)}
  ]
}];
