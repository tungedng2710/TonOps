import {provideEffects} from '@ngrx/effects';
import {CommonDashboardEffects} from './common-dashboard.effects';

export const commonDashboardProviders = [
  provideEffects([CommonDashboardEffects]),
];
