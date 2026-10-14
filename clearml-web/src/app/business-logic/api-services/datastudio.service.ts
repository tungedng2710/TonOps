import {inject, Injectable} from '@angular/core';
import {HttpHeaders} from '@angular/common/http';
import {Observable} from 'rxjs';
import {HTTP} from '~/app.constants';
import {SmApiRequestsService} from './api-requests.service';

export interface DataStudioConnection {
  configured: boolean;
  connected: boolean;
  username: string | null;
  checked_at: string | null;
  web_url: string;
}

export interface DataStudioRevision {
  revision_id: string;
  status: string;
  data_stage: string | null;
  commit_message: string;
  created_at: string;
  manifest_sha256: string;
}

export interface DataStudioDataset {
  id: string;
  namespace: string;
  slug: string;
  description: string;
  visibility: string;
  data_stage: string | null;
  tags: string[];
  updated_at: string;
  latest_revision: DataStudioRevision | null;
}

@Injectable({providedIn: 'root'})
export class ApiDataStudioService {
  private api = inject(SmApiRequestsService);
  private options = {headers: new HttpHeaders({'Accept': 'application/json'}), withCredentials: true};

  private post<T>(action: string, body: object = {}): Observable<T> {
    return this.api.post<T>(`${HTTP.API_BASE_URL}/datastudio.${action}`, body, this.options);
  }

  status() { return this.post<DataStudioConnection>('status'); }
  connect(username: string, token: string) { return this.post<DataStudioConnection>('connect', {username, token}); }
  disconnect() { return this.post<DataStudioConnection>('disconnect'); }
  datasets() { return this.post<{items: DataStudioDataset[]; connection: DataStudioConnection}>('datasets'); }
  revisions(namespace: string, dataset: string) {
    return this.post<{revisions: DataStudioRevision[]}>('revisions', {namespace, dataset});
  }
}
