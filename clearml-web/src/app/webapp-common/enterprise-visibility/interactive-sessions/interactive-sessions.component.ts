import {Component} from '@angular/core';
import {NgOptimizedImage} from '@angular/common';
import {PageBaseComponent} from '@common/enterprise-visibility/page-base.component';

@Component({
    selector: 'sm-interactive-sessions',
    imports: [
        NgOptimizedImage
    ],
    templateUrl: './interactive-sessions.component.html',
    styleUrl: '../pages.scss'
})
export class InteractiveSessionsComponent extends PageBaseComponent {
}
