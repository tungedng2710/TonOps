import {Routes} from '@angular/router';
import {CrumbTypeEnum} from '@common/layout/breadcrumbs/breadcrumbs.component';
import {settingsProviders} from '~/features/settings/settings.providers';
import {iamAdminGuard} from '~/features/settings/iam/iam-admin.guard';

const settingsBreadcrumb = {
  name: 'Settings',
  url: 'settings',
  type: CrumbTypeEnum.Feature
};

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./settings.component').then(m => m.SettingsComponent),
    providers: settingsProviders,
    children: [
      {
        path: '',
        redirectTo: 'account',
        pathMatch: 'full'
      },
      {path: 'profile', redirectTo: 'account', pathMatch: 'full'},
      {path: 'account',
        loadComponent: () => import('./containers/admin/profile-name/profile-name.component').then(m => m.ProfileNameComponent),
        data: {
        staticBreadcrumb:[[settingsBreadcrumb, {
            name: 'Account settings',
            type: CrumbTypeEnum.SubFeature
          }]]},
      },
      {
        path: 'webapp-configuration',
        loadComponent: () => import('~/features/settings/containers/webapp-configuration/webapp-configuration.component').then(m => m.WebappConfigurationComponent),
        data: {workspaceNeutral: true, staticBreadcrumb:[[settingsBreadcrumb, {
            name: 'Configuration',
            type: CrumbTypeEnum.SubFeature
          }]]},
      },
      {
        path: 'workspace-configuration',
        redirectTo: 'account',
        pathMatch: 'full'
      },
      {
        path: 'user-management',
        canActivate: [iamAdminGuard],
        loadComponent: () => import('~/features/settings/iam/iam-management.component').then(m => m.IamManagementComponent),
        data: {workspaceNeutral: true, staticBreadcrumb:[[settingsBreadcrumb, {
            name: 'User Management',
            type: CrumbTypeEnum.SubFeature
          }]]},
      },
      {
        path: 'storage-credentials',
        loadComponent: () => import('@common/settings/storage-credentials/storage-credentials.component').then(m => m.StorageCredentialsComponent),
        data: {
          workspaceNeutral: true,
          route: '/settings/storage-credentials',
          staticBreadcrumb: [[settingsBreadcrumb, {
            name: 'Storage Cleanup',
            type: CrumbTypeEnum.SubFeature
          }]]
        }
      }
    ]
  }
];
