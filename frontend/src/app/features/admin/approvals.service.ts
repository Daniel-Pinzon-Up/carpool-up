import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { DocKind, ReviewStatus, UserRole, UserStatus } from '../../core/auth/auth.models';

export type ApprovalType = 'identity' | 'license';

export interface ApprovalItem {
  id: string;
  type: ApprovalType;
  doc_kind: DocKind | null;
  status: ReviewStatus;
  submitted_at: string;
  reviewed_at: string | null;
  rejection_reason: string | null;
  semester: string | null;
  license_expires_on: string | null;
  applicant: {
    id: string;
    full_name: string;
    program: string | null;
    role: UserRole;
    sex: 'female' | 'male';
    status: UserStatus;
  };
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

const BASE = '/api/v1/admin';

@Injectable({ providedIn: 'root' })
export class ApprovalsApi {
  private readonly http = inject(HttpClient);

  queue(type: ApprovalType, cursor?: string): Promise<Page<ApprovalItem>> {
    const params: Record<string, string> = { type, limit: '30' };
    if (cursor) params['cursor'] = cursor;
    return firstValueFrom(this.http.get<Page<ApprovalItem>>(`${BASE}/approvals`, { params }));
  }

  counts(): Promise<Record<ApprovalType, number>> {
    return firstValueFrom(this.http.get<Record<ApprovalType, number>>(`${BASE}/approvals/counts`));
  }

  approve(id: string, sex: 'female' | 'male' | null): Promise<ApprovalItem> {
    return firstValueFrom(
      this.http.post<ApprovalItem>(`${BASE}/approvals/${id}/approve`, sex ? { sex } : {}),
    );
  }

  reject(id: string, reason: string): Promise<ApprovalItem> {
    return firstValueFrom(
      this.http.post<ApprovalItem>(`${BASE}/approvals/${id}/reject`, { reason }),
    );
  }

  filePath(id: string): string {
    return `${BASE}/files/${id}`;
  }
}
