import {Component} from '@angular/core';
import {NgOptimizedImage} from '@angular/common';
import {PageBaseComponent} from '@common/enterprise-visibility/page-base.component';

@Component({
    selector: 'sm-security',
    imports: [
        NgOptimizedImage
    ],
    templateUrl: './security.component.html',
    styleUrl: '../pages.scss'
})
export class SecurityComponent extends PageBaseComponent {
}
