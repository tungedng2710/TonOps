import { Component } from '@angular/core';
import {ProfilePreferencesComponent} from '@common/settings/admin/profile-preferences/profile-preferences.component';

@Component({
    selector: 'sm-webapp-configuration',
    imports: [
        ProfilePreferencesComponent,
    ],
    templateUrl: './webapp-configuration.component.html',
    styleUrl: './webapp-configuration.component.scss'
})
export class WebappConfigurationComponent {

}
