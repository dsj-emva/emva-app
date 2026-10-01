export interface paths {
    "/advertisers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Advertiser */
        post: operations["createAdvertiser"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Advertiser */
        get: operations["getAdvertiser"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}/files/{kind}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Upload File
         * @description Upload the file, replacing any earlier upload of the same kind.
         */
        put: operations["uploadFile"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}/files/{kind}/columns": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Columns
         * @description Each column of the file with its first few values, read from the file itself; gone once
         *     the file is formatted.
         */
        get: operations["getColumns"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}/mapping": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Mapping
         * @description The mapping as last saved (an empty draft at first), with what stops it being confirmed.
         */
        get: operations["getMapping"];
        /**
         * Save Mapping
         * @description Keep the draft as it stands; refused once the mapping is confirmed.
         */
        put: operations["saveMapping"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}/mapping/confirmation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Confirm Mapping
         * @description Confirm the saved draft, recording when, and format both files with it in the same
         *     operation; refused while it has problems. The formatted data and the confirmation are saved
         *     together or not at all; then each raw file is deleted, and recorded as deleted, in turn.
         *
         *     Confirming again finishes what was interrupted: it formats a mapping confirmed before its
         *     data was formatted, while the raw files are there, and deletes raw files still kept.
         */
        post: operations["confirmMapping"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["getHealth"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** Advertiser */
        Advertiser: {
            data_source: components["schemas"]["DataSource"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            leads_file: components["schemas"]["FileProfile"] | null;
            /**
             * Mapping Confirmed At
             * @description When the mapping was confirmed; from then on the files cannot be replaced
             */
            mapping_confirmed_at: string | null;
            /** Name */
            name: string;
            /**
             * Review Available
             * @description True once both files are uploaded
             */
            review_available: boolean;
            stage_history_file: components["schemas"]["FileProfile"] | null;
        };
        /** Column */
        Column: {
            /**
             * Examples
             * @description The column's first few distinct non-empty values
             */
            examples: string[];
            /** Name */
            name: string;
        };
        /**
         * ColumnKind
         * @description How an input column is read: as a number, or as one of a set of categories.
         * @enum {string}
         */
        ColumnKind: "number" | "category";
        /** CrmStage */
        CrmStage: {
            /** Name */
            name: string;
            /** Row Count */
            row_count: number;
        };
        /**
         * DataSource
         * @description Where an advertiser's data comes from; every result is labelled with it.
         * @enum {string}
         */
        DataSource: "hand_made_test" | "simulated" | "public" | "private";
        /**
         * DateOrder
         * @enum {string}
         */
        DateOrder: "year_month_day" | "day_month_year" | "month_day_year";
        /** DateOrderChoice */
        DateOrderChoice: {
            /** Label */
            label: string;
            value: components["schemas"]["DateOrder"];
        };
        /**
         * FileKind
         * @enum {string}
         */
        FileKind: "leads" | "stage-history";
        /** FileProfile */
        FileProfile: {
            /** Column Names */
            column_names: string[];
            /** File Name */
            file_name: string;
            kind: components["schemas"]["FileKind"];
            /**
             * Raw Kept
             * @description Whether the raw file is still in storage; false once formatted and deleted
             */
            raw_kept: boolean;
            /** Row Count */
            row_count: number;
            /**
             * Uploaded At
             * Format: date-time
             */
            uploaded_at: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** Health */
        Health: {
            /**
             * Status
             * @constant
             */
            status: "ok";
        };
        /** InputKindChoice */
        InputKindChoice: {
            kind: components["schemas"]["ColumnKind"];
            /** Label */
            label: string;
        };
        /**
         * LeadsColumns
         * @description Which leads-file column holds what. Every column not marked here is dropped.
         */
        LeadsColumns: {
            /**
             * Country
             * @description The lead's country, used only to read its phone, then dropped
             */
            country?: string | null;
            /**
             * Currency
             * @description The lead's currency, used only to read its phone, then dropped
             */
            currency?: string | null;
            /**
             * Email
             * @description The lead's email, to be scrambled
             */
            email?: string | null;
            /**
             * Inputs
             * @description The inputs to the score, each read as its kind
             */
            inputs?: {
                [key: string]: components["schemas"]["ColumnKind"];
            };
            /** Lead Id */
            lead_id?: string | null;
            /**
             * Name
             * @description The lead's name, to be removed
             */
            name?: string | null;
            /**
             * Phone
             * @description The lead's phone, to be scrambled
             */
            phone?: string | null;
            /**
             * Submitted At
             * @description When the lead was submitted
             */
            submitted_at?: string | null;
        };
        /**
         * LeadsRole
         * @description What a leads-file column can hold besides an input; each is a field of LeadsColumns.
         * @enum {string}
         */
        LeadsRole: "lead_id" | "submitted_at" | "name" | "email" | "phone" | "country" | "currency";
        /** LeadsRoleChoice */
        LeadsRoleChoice: {
            /** Label */
            label: string;
            role: components["schemas"]["LeadsRole"];
        };
        /** Mapping */
        Mapping: {
            /**
             * Crm Stages
             * @description Where each CRM stage name sits: a Stage, or Lost
             */
            crm_stages?: {
                [key: string]: components["schemas"]["StageOrLost"];
            };
            /** @description The order both files write dates in */
            date_order?: components["schemas"]["DateOrder"] | null;
            /**
             * @default {
             *       "inputs": {}
             *     }
             */
            leads: components["schemas"]["LeadsColumns"];
            /** @default {} */
            stage_history: components["schemas"]["StageHistoryColumns"];
            /**
             * Time Zone
             * @description The zone of every time written without one
             * @default UTC
             */
            time_zone: string;
            /** Typical Deal Size */
            typical_deal_size?: number | null;
        };
        /** MappingReview */
        MappingReview: {
            /**
             * Confirmed At
             * @description When a person confirmed it; null in draft
             */
            confirmed_at: string | null;
            /**
             * Crm Stages
             * @description Every CRM stage name in the column marked as the CRM stage, most used first
             */
            crm_stages: components["schemas"]["CrmStage"][];
            /**
             * Date Orders
             * @description The orders dates can be written in
             */
            date_orders: components["schemas"]["DateOrderChoice"][];
            /**
             * Formatted At
             * @description When its data was formatted
             */
            formatted_at: string | null;
            /** @description What formatting made of the files */
            formatting: components["schemas"]["Summary"] | null;
            /**
             * Input Kinds
             * @description How an input column can be read
             */
            input_kinds: components["schemas"]["InputKindChoice"][];
            /**
             * Leads Roles
             * @description What a leads-file column can hold
             */
            leads_roles: components["schemas"]["LeadsRoleChoice"][];
            mapping: components["schemas"]["Mapping"];
            /**
             * Problems
             * @description Why it cannot be confirmed yet; empty once it can
             */
            problems: string[];
            /**
             * Stage History Roles
             * @description What a stage-history column can hold
             */
            stage_history_roles: components["schemas"]["StageHistoryRoleChoice"][];
            /**
             * Stages And Lost
             * @description What a CRM stage can be placed on: the Canonical ladder in order, then Lost
             */
            stages_and_lost: components["schemas"]["StageOrLostChoice"][];
            /**
             * Still To Do
             * @description What confirming still has to do, when it was interrupted; confirming again does it. Null in draft and once confirming is done.
             */
            still_to_do: string | null;
        };
        /** NewAdvertiser */
        NewAdvertiser: {
            data_source: components["schemas"]["DataSource"];
            /** Name */
            name: string;
        };
        /** Problem */
        Problem: {
            /** Detail */
            detail: string;
        };
        /**
         * Stage
         * @description A Stage of the Canonical ladder; members are in ladder order.
         * @enum {string}
         */
        Stage: "submitted" | "contact_attempted" | "engaged" | "qualified" | "proposal" | "won";
        /** StageHistoryColumns */
        StageHistoryColumns: {
            /**
             * Changed At
             * @description When the change of CRM stage happened
             */
            changed_at?: string | null;
            /** Crm Stage */
            crm_stage?: string | null;
            /** Deal Value */
            deal_value?: string | null;
            /** Lead Id */
            lead_id?: string | null;
        };
        /**
         * StageHistoryRole
         * @description What a stage-history column can hold; each is a field of StageHistoryColumns.
         * @enum {string}
         */
        StageHistoryRole: "lead_id" | "crm_stage" | "changed_at" | "deal_value";
        /** StageHistoryRoleChoice */
        StageHistoryRoleChoice: {
            /** Label */
            label: string;
            role: components["schemas"]["StageHistoryRole"];
        };
        StageOrLost: components["schemas"]["Stage"] | "lost";
        /** StageOrLostChoice */
        StageOrLostChoice: {
            /** Name */
            name: string;
            value: components["schemas"]["StageOrLost"];
        };
        /**
         * Summary
         * @description What the Formatter made of the two files.
         */
        Summary: {
            /** Lead Count */
            lead_count: number;
            /** Lost */
            lost: number;
            /**
             * Neglected
             * @description Neglected leads: never attempted to contact
             */
            neglected: number;
            /**
             * No Outcome Yet
             * @description Leads neither won nor lost yet
             */
            no_outcome_yet: number;
            /**
             * Phones Without Country
             * @description Leads whose phone's country was not found, so its digits as written were hashed; to be resolved later
             */
            phones_without_country: number;
            /** Unreadable */
            unreadable: components["schemas"]["UnreadableRows"][];
            /** Won */
            won: number;
        };
        /**
         * UnreadableRows
         * @description The rows of one file that could not be read for one reason, and so were not kept.
         */
        UnreadableRows: {
            /** Count */
            count: number;
            file: components["schemas"]["FileKind"];
            /**
             * First Rows
             * @description The first 10 of them, by place in the file from 1 below the header
             */
            first_rows: number[];
            /** Reason */
            reason: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    createAdvertiser: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["NewAdvertiser"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Advertiser"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    getAdvertiser: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                advertiser_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Advertiser"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    uploadFile: {
        parameters: {
            query: {
                file_name: string;
            };
            header?: never;
            path: {
                advertiser_id: string;
                kind: components["schemas"]["FileKind"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "text/csv": Blob;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FileProfile"];
                };
            };
            /** @description Not a readable CSV file */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Another upload won, or the mapping is confirmed */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Over 20 MB */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Not saved */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    getColumns: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                advertiser_id: string;
                kind: components["schemas"]["FileKind"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Column"][];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Stored file unreadable */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Formatted, and so deleted */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    getMapping: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                advertiser_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MappingReview"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Stored file unreadable */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    saveMapping: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                advertiser_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Mapping"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MappingReview"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Already confirmed, or a stored file is unreadable */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    confirmMapping: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                advertiser_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MappingReview"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Not confirmable yet, already confirmed, or a file cannot be read */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Not confirmed, or confirmed but the raw files not all deleted yet */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    getHealth: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Health"];
                };
            };
        };
    };
}
