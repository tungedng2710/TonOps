import {Routes} from '@angular/router';
import {EntityTypeEnum} from '~/shared/constants/non-common-consts';
import {resetContextMenuGuard} from '@common/shared/guards/resetContextMenuGuard.guard';
import {CrumbTypeEnum} from '@common/layout/breadcrumbs/breadcrumbs.component';

export const routes: Routes = [{
  path: '',
  loadComponent: () => import('./model-management.component').then(c => c.ModelManagementComponent),
  data: {modelManagement: true, staticBreadcrumb: [[{name: 'Model management', type: CrumbTypeEnum.Feature}]]},
  children: [
    {path: '', pathMatch: 'full', redirectTo: 'registry/*'},
    {path: 'registry', pathMatch: 'full', redirectTo: 'registry/*'},
    {
      path: 'registry/:projectId',
      data: {modelManagement: true, modelRegistry: true, autoSearchTab: 'models'},
      loadChildren: () => import('@common/models/models.routes').then(r => r.routes),
      canDeactivate: [resetContextMenuGuard]
    },
    {
      path: 'endpoints', data: {modelManagement: true, autoSearchTab: 'modelEndpoints'},
      loadChildren: () => import('@common/serving/serving.routes').then(r => r.routes),
      canDeactivate: [resetContextMenuGuard]
    },
    {
      path: 'compare-models/:projectId',
      data: {modelManagement: true, entityType: EntityTypeEnum.model, autoSearchTab: 'models', search: false},
      loadChildren: () => import('@common/experiments-compare/experiments-compare.routes').then(r => r.routes)
    }
  ]
}];
