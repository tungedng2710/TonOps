import {inject} from '@angular/core';
import {RedirectFunction, Router, Routes} from '@angular/router';

const redirectModels: RedirectFunction = ({params, url, queryParams, fragment}) => {
  const suffix = url.length ? '/' + url.map(segment => segment.toString()).join('/') : '';
  const target = inject(Router).parseUrl(`/models/registry/${encodeURIComponent(params.projectId || '*')}${suffix}`);
  target.queryParams = queryParams;
  target.fragment = fragment;
  return target;
};

const redirectEndpoints: RedirectFunction = ({url, queryParams, fragment}) => {
  const target = inject(Router).parseUrl(`/models/endpoints/${url.length ? url.map(segment => segment.toString()).join('/') : 'active'}`);
  target.queryParams = queryParams;
  target.fragment = fragment;
  return target;
};

export const legacyModelRoutes: Routes = [{path: '**', redirectTo: redirectModels}];
export const legacyEndpointRoutes: Routes = [{path: '**', redirectTo: redirectEndpoints}];
export const legacyComparisonRoutes: Routes = [{path: '**', redirectTo: ({params, url, queryParams, fragment}) => {
  const suffix = url.length ? '/' + url.map(segment => segment.toString()).join('/') : '';
  const target = inject(Router).parseUrl(`/models/compare-models/${encodeURIComponent(params.projectId || '*')}${params.ids ? ';ids=' + encodeURIComponent(params.ids) : ''}${suffix}`);
  target.queryParams = queryParams;
  target.fragment = fragment;
  return target;
}}];
