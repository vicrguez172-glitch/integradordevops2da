import { CommonModule, CurrencyPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { finalize, switchMap } from 'rxjs';

import { ScrollRevealDirective } from './scroll-reveal.directive';
import { Game, Purchase, StoreApiService, StoreUser } from './store-api.service';

type StoreView = 'store' | 'cart' | 'account' | 'admin';
type AuthMode = 'login' | 'register';
type FeedbackKind = 'success' | 'error';

type PendingDelete =
  | { kind: 'user'; user: StoreUser }
  | { kind: 'game'; game: Game }
  | null;

interface CartLine {
  game: Game;
  quantity: number;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, CurrencyPipe, ScrollRevealDirective],
  templateUrl: './app.html',
})
export class App implements OnInit {
  private readonly api = inject(StoreApiService);

  readonly games = signal<Game[]>([]);
  readonly user = signal<StoreUser | null>(null);
  readonly view = signal<StoreView>('store');
  readonly modal = signal<'auth' | 'checkout' | 'game' | null>(null);
  readonly feedback = signal<{ kind: FeedbackKind; message: string } | null>(null);
  readonly pendingDelete = signal<PendingDelete>(null);
  readonly authMode = signal<AuthMode>('login');
  readonly cart = signal<CartLine[]>(this.readCart());
  readonly purchases = signal<Purchase[]>([]);
  readonly users = signal<StoreUser[]>([]);
  readonly loading = signal(false);
  readonly searchText = signal('');
  readonly selectedCategory = signal('Todos');
  readonly userSearch = signal('');
  readonly userRoleFilter = signal('all');
  readonly userStatusFilter = signal('all');
  readonly inventorySearch = signal('');
  readonly inventoryCategoryFilter = signal('Todos');
  readonly inventoryPlatformFilter = signal('Todas');
  readonly passwordVisibility = signal<Record<string, boolean>>({});
  readonly gameEditorOpen = signal(false);
  readonly editingGameId = signal<number | null>(null);
  readonly editingUserId = signal<number | null>(null);
  readonly cartCount = computed(() => this.cart().reduce((sum, line) => sum + line.quantity, 0));
  readonly cartTotal = computed(() =>
    this.cart().reduce((sum, line) => sum + Number(line.game.price) * line.quantity, 0),
  );
  readonly categories = computed(() => [
    'Todos',
    ...new Set(this.games().map((game) => game.category)),
  ]);
  readonly filteredGames = computed(() => {
    const search = this.searchText().trim().toLocaleLowerCase();
    return this.games().filter((game) => {
      const matchesSearch =
        !search ||
        `${game.title} ${game.description} ${game.platform} ${game.category}`
          .toLocaleLowerCase()
          .includes(search);
      return (
        matchesSearch &&
        (this.selectedCategory() === 'Todos' || game.category === this.selectedCategory())
      );
    });
  });
  readonly filteredUsers = computed(() => {
    const search = this.userSearch().trim().toLocaleLowerCase();
    return this.users().filter((user) => {
      const matchesSearch =
        !search || `${user.full_name} ${user.email}`.toLocaleLowerCase().includes(search);
      return (
        matchesSearch &&
        (this.userRoleFilter() === 'all' || user.role === this.userRoleFilter()) &&
        (this.userStatusFilter() === 'all' ||
          user.is_active === (this.userStatusFilter() === 'active'))
      );
    });
  });
  readonly inventoryPlatforms = computed(() => [
    'Todas',
    ...new Set(this.games().map((game) => game.platform)),
  ]);
  readonly filteredInventoryGames = computed(() => {
    const search = this.inventorySearch().trim().toLocaleLowerCase();
    return this.games().filter((game) => {
      const matchesSearch =
        !search ||
        `${game.title} ${game.description} ${game.platform} ${game.category}`
          .toLocaleLowerCase()
          .includes(search);
      return (
        matchesSearch &&
        (this.inventoryCategoryFilter() === 'Todos' ||
          game.category === this.inventoryCategoryFilter()) &&
        (this.inventoryPlatformFilter() === 'Todas' ||
          game.platform === this.inventoryPlatformFilter())
      );
    });
  });

  loginForm = { email: '', password: '' };
  registerForm = { email: '', full_name: '', password: '' };
  gameForm: Omit<Game, 'id'> = this.emptyGame();
  userForm: { email: string; full_name: string; password: string; role: StoreUser['role'] } = {
    email: '',
    full_name: '',
    password: '',
    role: 'customer',
  };
  userEditForm: {
    email: string;
    full_name: string;
    password: string;
    role: StoreUser['role'];
  } = { email: '', full_name: '', password: '', role: 'customer' };

  ngOnInit(): void {
    this.loadGames();
    if (this.api.hasSession()) {
      this.api.currentUser().subscribe({
        next: (user) => this.user.set(user),
        error: () => this.api.logout(),
      });
    }
  }

  loadGames(): void {
    this.api.games().subscribe({
      next: (games) => this.games.set(games),
      error: () => this.showError('No se pudo cargar el catálogo. Verifica que la API esté activa.'),
    });
  }

  openAuth(mode: AuthMode = 'login'): void {
    this.authMode.set(mode);
    this.modal.set('auth');
  }

  closeModal(): void {
    this.modal.set(null);
  }

  scrollTo(id: string): void {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  }

  openStorePage(): void {
    this.view.set('store');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  openCart(): void {
    this.view.set('cart');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  scrollToTop(): void {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  isPasswordVisible(field: string): boolean {
    return this.passwordVisibility()[field] ?? false;
  }

  togglePasswordVisibility(field: string): void {
    this.passwordVisibility.update((visibility) => ({
      ...visibility,
      [field]: !visibility[field],
    }));
  }

  submitLogin(): void {
    this.loading.set(true);
    this.api
      .login(this.loginForm)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (result) => {
          this.user.set(result.user);
          this.loginForm.password = '';
          this.closeModal();
          this.showNotice(`¡Hola, ${result.user.full_name}!`);
          if (result.user.role === 'admin') this.loadAdminUsers();
        },
        error: (error: unknown) =>
          this.showError(this.apiErrorMessage(error, 'No se pudo iniciar sesión. Intenta de nuevo.')),
      });
  }

  submitRegister(): void {
    this.loading.set(true);
    const credentials = { email: this.registerForm.email, password: this.registerForm.password };
    this.api
      .register(this.registerForm)
      .pipe(
        switchMap(() => this.api.login(credentials)),
        finalize(() => this.loading.set(false)),
      )
      .subscribe({
        next: (result) => {
          this.user.set(result.user);
          this.registerForm = { email: '', full_name: '', password: '' };
          this.closeModal();
          this.showNotice('Tu cuenta está lista. ¡Bienvenido a Nivel!');
        },
        error: (error: unknown) =>
          this.showError(this.apiErrorMessage(error, 'No se pudo crear la cuenta. Intenta de nuevo.')),
      });
  }

  logout(): void {
    this.api.logout();
    this.user.set(null);
    this.view.set('store');
    this.showNotice('Sesión cerrada.');
  }

  addToCart(game: Game): void {
    if (game.stock < 1) return;
    const current = this.cart();
    const found = current.find((line) => line.game.id === game.id);
    if (found && found.quantity >= game.stock) {
      this.showError('Ya agregaste todas las existencias disponibles.');
      return;
    }
    const updated = found
      ? current.map((line) =>
          line.game.id === game.id ? { ...line, quantity: line.quantity + 1 } : line,
        )
      : [...current, { game, quantity: 1 }];
    this.saveCart(updated);
    this.showNotice(`${game.title} se agregó a tu carrito.`);
  }

  changeQuantity(gameId: number, change: number): void {
    const updated = this.cart()
      .map((line) =>
        line.game.id === gameId
          ? { ...line, quantity: Math.min(line.game.stock, line.quantity + change) }
          : line,
      )
      .filter((line) => line.quantity > 0);
    this.saveCart(updated);
  }

  removeFromCart(gameId: number): void {
    this.saveCart(this.cart().filter((line) => line.game.id !== gameId));
  }

  beginCheckout(): void {
    if (!this.cart().length) return;
    if (!this.user()) {
      this.openAuth();
      this.showError('Inicia sesión para finalizar tu compra.');
      return;
    }
    this.modal.set('checkout');
  }

  confirmPurchase(): void {
    this.loading.set(true);
    this.api
      .purchase({
        items: this.cart().map((line) => ({ game_id: line.game.id, quantity: line.quantity })),
      })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (purchase) => {
          this.saveCart([]);
          this.closeModal();
          this.view.set('account');
          this.loadPurchases();
          this.loadGames();
          this.showNotice(`Pedido #${purchase.id} confirmado. ¡Gracias por tu pedido!`);
        },
        error: (error: unknown) =>
          this.showError(this.apiErrorMessage(error, 'No se pudo procesar la compra.')),
      });
  }

  openAccount(): void {
    if (!this.user()) {
      this.openAuth();
      return;
    }
    this.view.set('account');
    this.loadPurchases();
  }

  openAdmin(): void {
    this.view.set('admin');
    this.loadAdminUsers();
  }

  loadPurchases(): void {
    this.api.purchases().subscribe({
      next: (purchases) => this.purchases.set(purchases),
      error: () => this.showError('No se pudo cargar tu historial de compras.'),
    });
  }

  loadAdminUsers(): void {
    if (this.user()?.role !== 'admin') return;
    this.api.users().subscribe({
      next: (users) => this.users.set(users),
      error: () => this.showError('No se pudo cargar la lista de usuarios.'),
    });
  }

  createUser(): void {
    this.api.createUser(this.userForm).subscribe({
      next: () => {
        this.userForm = { email: '', full_name: '', password: '', role: 'customer' };
        this.loadAdminUsers();
        this.showNotice('Usuario creado.');
      },
      error: (error: unknown) =>
        this.showError(this.apiErrorMessage(error, 'No se pudo crear el usuario.')),
    });
  }

  startUserEdit(user: StoreUser): void {
    this.editingUserId.set(user.id);
    this.userEditForm = {
      email: user.email,
      full_name: user.full_name,
      password: '',
      role: user.role,
    };
  }

  saveUserEdit(userId: number): void {
    const { password, ...userFields } = this.userEditForm;
    const changes = password ? { ...userFields, password } : userFields;
    this.api.updateUser(userId, changes).subscribe({
      next: (updatedUser) => {
        this.editingUserId.set(null);
        if (this.user()?.id === updatedUser.id) {
          this.user.set(updatedUser);
          if (updatedUser.role !== 'admin') this.view.set('store');
        }
        this.loadAdminUsers();
        this.showNotice('Usuario actualizado.');
      },
      error: (error: unknown) =>
        this.showError(this.apiErrorMessage(error, 'No se pudo actualizar el usuario.')),
    });
  }

  deleteUser(user: StoreUser): void {
    this.pendingDelete.set({ kind: 'user', user });
  }

  reactivateUser(user: StoreUser): void {
    this.api
      .updateUser(user.id, {
        email: user.email,
        full_name: user.full_name,
        role: user.role,
        is_active: true,
      })
      .subscribe({
        next: () => {
          this.loadAdminUsers();
          this.showNotice('Usuario reactivado.');
        },
        error: (error: unknown) =>
          this.showError(this.apiErrorMessage(error, 'No se pudo reactivar el usuario.')),
      });
  }

  deleteGame(game: Game): void {
    this.pendingDelete.set({ kind: 'game', game });
  }

  confirmDelete(): void {
    const pending = this.pendingDelete();
    if (!pending) return;
    this.pendingDelete.set(null);

    if (pending.kind === 'user') {
      this.api.deleteUser(pending.user.id).subscribe({
        next: () => {
          if (this.user()?.id === pending.user.id) {
            this.api.logout();
            this.user.set(null);
            this.view.set('store');
            this.showNotice('Tu cuenta fue dada de baja. Se cerró tu sesión.');
            return;
          }
          this.loadAdminUsers();
          this.showNotice('Usuario dado de baja. Sus compras se conservaron.');
        },
        error: (error: unknown) =>
          this.showError(this.apiErrorMessage(error, 'No se pudo eliminar el usuario.')),
      });
      return;
    }

    this.api.deleteGame(pending.game.id).subscribe({
      next: () => {
        this.loadGames();
        this.showNotice('Juego eliminado del catálogo.');
      },
      error: (error: unknown) =>
        this.showError(this.apiErrorMessage(error, 'No se pudo eliminar el juego.')),
    });
  }

  openNewGame(): void {
    this.editingGameId.set(null);
    this.gameForm = this.emptyGame();
    this.gameEditorOpen.set(true);
  }

  startGameEdit(game: Game): void {
    this.editingGameId.set(game.id);
    this.gameForm = {
      title: game.title,
      description: game.description,
      platform: game.platform,
      category: game.category,
      price: Number(game.price),
      image_url: game.image_url,
      stock: game.stock,
    };
    this.gameEditorOpen.set(true);
  }

  saveGame(): void {
    const gameId = this.editingGameId();
    const request = gameId
      ? this.api.updateGame(gameId, this.gameForm)
      : this.api.createGame(this.gameForm);
    request.subscribe({
      next: () => {
        this.gameEditorOpen.set(false);
        this.loadGames();
        this.showNotice(gameId ? 'Juego actualizado.' : 'Juego agregado al catálogo.');
      },
      error: (error: unknown) =>
        this.showError(this.apiErrorMessage(error, 'No se pudo guardar el juego.')),
    });
  }

  private saveCart(cart: CartLine[]): void {
    this.cart.set(cart);
    localStorage.setItem('nivel-cart', JSON.stringify(cart));
  }

  private readCart(): CartLine[] {
    try {
      const value = localStorage.getItem('nivel-cart');
      return value ? (JSON.parse(value) as CartLine[]) : [];
    } catch {
      return [];
    }
  }

  private emptyGame(): Omit<Game, 'id'> {
    return {
      title: '',
      description: '',
      platform: 'PC',
      category: 'Aventura',
      price: 0,
      image_url: '',
      stock: 1,
    };
  }

  private showError(message: string): void {
    this.feedback.set({ kind: 'error', message });
  }

  dismissFeedback(): void {
    this.feedback.set(null);
  }

  private apiErrorMessage(error: unknown, fallback: string): string {
    if (!(error instanceof HttpErrorResponse)) return fallback;

    const body: unknown = error.error;
    if (!body || typeof body !== 'object' || !('detail' in body)) return fallback;

    const detail: unknown = body.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (!Array.isArray(detail)) return fallback;

    const labels: Record<string, string> = {
      email: 'Correo electrónico',
      full_name: 'Nombre completo',
      title: 'Título',
      description: 'Descripción',
      platform: 'Plataforma',
      category: 'Categoría',
      price: 'Precio',
      image_url: 'URL de portada',
      stock: 'Existencias',
      role: 'Rol',
      password: 'Contraseña',
    };
    const messages = detail.flatMap((entry): string[] => {
      if (!entry || typeof entry !== 'object' || !('msg' in entry)) return [];
      const { msg } = entry;
      if (typeof msg !== 'string') return [];

      const rawLocation: unknown = 'loc' in entry ? entry.loc : undefined;
      const location = Array.isArray(rawLocation)
        ? rawLocation.filter(
            (part: unknown): part is string | number =>
              typeof part === 'string' || typeof part === 'number',
          )
        : [];
      const field = String(location[location.length - 1] ?? '');
      const label = labels[field] ?? field;
      return [label ? `${label}: ${msg}` : msg];
    });

    return messages.length ? `Revisa los datos ingresados: ${messages.join('; ')}` : fallback;
  }

  private showNotice(message: string): void {
    this.feedback.set({ kind: 'success', message });
  }
}
