import {inject, Injectable} from '@angular/core';
import {HttpHeaders} from '@angular/common/http';
import {Observable} from 'rxjs';
import {HTTP} from '~/app.constants';
import {SmApiRequestsService} from './api-requests.service';
import {IamAuditEvent, IamGroup, IamPage, IamServiceStatus, IamSignupRequest, IamUser} from '~/features/settings/iam/iam.models';

@Injectable({providedIn: 'root'})
export class ApiIamService {
  private api = inject(SmApiRequestsService);
  private basePath = HTTP.API_BASE_URL;
  private options = {headers: new HttpHeaders({'Accept': 'application/json'}), withCredentials: true};

  private post<T>(action: string, body: object = {}): Observable<T> {
    return this.api.post<T>(`${this.basePath}/iam.${action}`, body, this.options);
  }

  status() { return this.post<IamServiceStatus>('status'); }
  signup(request: IamSignupRequest) { return this.post<{user: IamUser}>('signup', request); }
  me() { return this.post<{user: IamUser}>('me'); }
  listUsers(request: object) { return this.post<IamPage<IamUser>>('list_users', request); }
  getUser(userId: string) { return this.post<{user: IamUser}>('get_user', {user_id: userId}); }
  createUser(request: object) { return this.post<{user: IamUser}>('create_user', request); }
  updateUser(userId: string, request: object) { return this.post<{user: IamUser}>('update_user', {user_id: userId, ...request}); }
  disableUser(userId: string) { return this.post<{user: IamUser}>('disable_user', {user_id: userId}); }
  enableUser(userId: string) { return this.post<{user: IamUser}>('enable_user', {user_id: userId}); }
  deleteUser(userId: string) { return this.post<{deleted: number}>('delete_user', {user_id: userId}); }
  resetPassword(userId: string, password?: string) {
    return this.post<{updated: number; temporary_password?: string}>('reset_password', {
      user_id: userId,
      ...(password ? {password} : {})
    });
  }
  changePassword(currentPassword: string, newPassword: string) {
    return this.post<{updated: number}>('change_password', {current_password: currentPassword, new_password: newPassword});
  }
  listGroups(request: object) { return this.post<IamPage<IamGroup>>('list_groups', request); }
  getGroup(groupId: string) { return this.post<{group: IamGroup}>('get_group', {group_id: groupId}); }
  createGroup(request: object) { return this.post<{group: IamGroup}>('create_group', request); }
  updateGroup(groupId: string, request: object) { return this.post<{group: IamGroup}>('update_group', {group_id: groupId, ...request}); }
  deleteGroup(groupId: string) { return this.post<{deleted: number}>('delete_group', {group_id: groupId}); }
  addGroupMember(groupId: string, userId: string) { return this.post<{added: number}>('add_group_member', {group_id: groupId, user_id: userId}); }
  removeGroupMember(groupId: string, userId: string) { return this.post<{removed: number}>('remove_group_member', {group_id: groupId, user_id: userId}); }
  listAudit(request: object) { return this.post<IamPage<IamAuditEvent>>('list_audit', request); }
}
