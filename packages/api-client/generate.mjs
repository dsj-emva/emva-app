// Generates src/schema.ts from openapi.json. Binary bodies (uploaded files) are typed as Blob, so a
// file the person picks is sent as it is, byte for byte.
import { writeFileSync } from 'node:fs'

import openapiTS, { astToString } from 'openapi-typescript'
import ts from 'typescript'

const BLOB = ts.factory.createTypeReferenceNode(ts.factory.createIdentifier('Blob'))

const ast = await openapiTS(new URL('./openapi.json', import.meta.url), {
  transform(schemaObject) {
    if (schemaObject.format === 'binary') return BLOB
  },
})

writeFileSync(new URL('./src/schema.ts', import.meta.url), astToString(ast))
