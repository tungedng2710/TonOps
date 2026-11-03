import {ChangeDetectionStrategy, Component, inject} from '@angular/core';
import {NgOptimizedImage} from '@angular/common';
import {ConfigurationService} from '../../shared/services/configuration.service';

@Component({
  selector: 'sm-auth-showcase',
  templateUrl: './auth-showcase.component.html',
  styleUrls: ['./auth-showcase.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgOptimizedImage]
})
export class AuthShowcaseComponent {
  protected environment = inject(ConfigurationService).configuration;
}
