import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, tap } from 'rxjs';

export interface StoreUser {
  id: number;
  email: string;
  full_name: string;
  role: 'admin' | 'customer';
  is_active: boolean;
  created_at: string;
}

export interface Game {
  id: number;
  title: string;
  description: string;
  platform: string;
  category: string;
  price: number;
  image_url: string;
  stock: number;
}

export interface Purchase {
  id: number;
  total: number;
  status: string;
  created_at: string;
  items: Array<{
    game_id: number;
    game_title: string;
    quantity: number;
    unit_price: number;
  }>;
}

interface AuthResponse {
  access_token: string;
  token_type: string;
  user: StoreUser;
}

@Injectable({ providedIn: 'root' })
export class StoreApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api';

  hasSession(): boolean {
    return Boolean(localStorage.getItem('nivel-token'));
  }

  login(credentials: { email: string; password: string }): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${this.base}/auth/login`, credentials)
      .pipe(tap((result) => localStorage.setItem('nivel-token', result.access_token)));
  }

  register(payload: { email: string; full_name: string; password: string }): Observable<StoreUser> {
    return this.http.post<StoreUser>(`${this.base}/auth/register`, payload);
  }

  currentUser(): Observable<StoreUser> {
    return this.http.get<StoreUser>(`${this.base}/auth/me`, { headers: this.authHeaders() });
  }

  logout(): void {
    localStorage.removeItem('nivel-token');
  }

  games(): Observable<Game[]> {
    return this.http.get<Game[]>(`${this.base}/games`);
  }

  users(): Observable<StoreUser[]> {
    return this.http.get<StoreUser[]>(`${this.base}/users`, { headers: this.authHeaders() });
  }

  createUser(payload: {
    email: string;
    full_name: string;
    password: string;
    role: StoreUser['role'];
  }): Observable<StoreUser> {
    return this.http.post<StoreUser>(`${this.base}/users`, payload, {
      headers: this.authHeaders(),
    });
  }

  updateUser(
    id: number,
    payload: {
      email: string;
      full_name: string;
      role: StoreUser['role'];
      password?: string;
      is_active?: boolean;
    },
  ): Observable<StoreUser> {
    return this.http.patch<StoreUser>(`${this.base}/users/${id}`, payload, {
      headers: this.authHeaders(),
    });
  }

  deleteUser(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/users/${id}`, { headers: this.authHeaders() });
  }

  createGame(payload: Omit<Game, 'id'>): Observable<Game> {
    return this.http.post<Game>(`${this.base}/games`, payload, { headers: this.authHeaders() });
  }

  updateGame(id: number, payload: Omit<Game, 'id'>): Observable<Game> {
    return this.http.patch<Game>(`${this.base}/games/${id}`, payload, {
      headers: this.authHeaders(),
    });
  }

  deleteGame(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/games/${id}`, { headers: this.authHeaders() });
  }

  purchase(payload: { items: Array<{ game_id: number; quantity: number }> }): Observable<Purchase> {
    return this.http.post<Purchase>(`${this.base}/purchases`, payload, {
      headers: this.authHeaders(),
    });
  }

  purchases(): Observable<Purchase[]> {
    return this.http.get<Purchase[]>(`${this.base}/purchases`, { headers: this.authHeaders() });
  }

  private authHeaders(): HttpHeaders {
    const token = localStorage.getItem('nivel-token');
    return token ? new HttpHeaders({ Authorization: `Bearer ${token}` }) : new HttpHeaders();
  }
}
