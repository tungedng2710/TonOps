import {inject, Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {firstValueFrom} from 'rxjs';
import {ApiModelsService} from '~/business-logic/api-services/models.service';
import {ConfigurationService} from '@common/shared/services/configuration.service';
import {ModelsCreateRequest} from '~/business-logic/model/models/modelsCreateRequest';

@Injectable({providedIn: 'root'})
export class ModelRegistryService {
  private models = inject(ApiModelsService);
  private http = inject(HttpClient);
  private configuration = inject(ConfigurationService);

  get uploadServer(): string | null {
    const server = this.configuration.fileServerUrl();
    return server && /^https?:\/\//.test(server) ? server.replace(/\/$/, '') : null;
  }

  async create(request: ModelsCreateRequest): Promise<string> {
    const response = await firstValueFrom(this.models.modelsCreate(request));
    if (!response.id) throw new Error('The server did not return a model ID. Refresh the registry before retrying.');
    return response.id;
  }

  async upload(file: File, uri: string): Promise<void> {
    // The server authorizes uploads against an existing registered model URI.
    const server = this.uploadServer;
    if (!server || !uri.startsWith(server + '/')) throw new Error('The fileserver configuration changed. Reopen the registry before uploading.');
    const path = decodeURIComponent(uri.slice(server.length + 1));
    const form = new FormData();
    form.append(path, file);
    const result = await firstValueFrom(this.http.post<string[]>(server + '/', form, {withCredentials: true}));
    if (!Array.isArray(result) || !result.includes(path)) throw new Error('The fileserver did not confirm the uploaded file. Retry this draft.');
  }
}
