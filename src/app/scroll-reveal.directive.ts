import { isPlatformBrowser } from '@angular/common';
import { Directive, ElementRef, OnDestroy, OnInit, PLATFORM_ID, inject } from '@angular/core';

@Directive({
  selector: '[appScrollReveal]',
  standalone: true,
})
export class ScrollRevealDirective implements OnInit, OnDestroy {
  private readonly element = inject(ElementRef<HTMLElement>).nativeElement;
  private readonly platformId = inject(PLATFORM_ID);
  private observer?: IntersectionObserver;

  ngOnInit(): void {
    if (
      !isPlatformBrowser(this.platformId) ||
      typeof IntersectionObserver === 'undefined' ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      this.element.classList.add('scroll-reveal-visible');
      return;
    }

    this.element.classList.add('scroll-reveal');
    this.observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          this.element.classList.add('scroll-reveal-visible');
          this.observer?.unobserve(this.element);
        }
      },
      { threshold: 0.12, rootMargin: '0px 0px -36px 0px' },
    );
    this.observer.observe(this.element);
  }

  ngOnDestroy(): void {
    this.observer?.disconnect();
  }
}
