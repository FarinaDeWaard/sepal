const {Subject, pipe} = require('rxjs')
const {finalize, takeUntil, switchMap, mergeMap, tap} = require('rxjs/operators')
const service = require('@sepal/worker/service')
const log = require('./log')('token')

const withToken$ = (servicePath, observable$) => {
    const releaseToken$ = new Subject()
    const token$ = service.request$(servicePath)

    const msg = ({requestId, rateToken, concurrencyToken}) =>
        `[Token.${requestId.substr(-4)}.R${rateToken}.C${concurrencyToken}]`
    
    const releaseToken = token => {
        releaseToken$.next()
        log.debug(`Returning token ${msg(token)}`)
    }
    
    return token$.pipe(
        tap(token => log.debug(`Using token ${msg(token)}`)),
        mergeMap(token =>
            observable$.pipe(
                finalize(() => releaseToken(token))
            )
        ),
        takeUntil(releaseToken$)
    )
}

const withToken = (servicePath, func$) =>
    pipe(
        switchMap(
            value => withToken$(servicePath, func$(value))
        )
    )

module.exports = {withToken$, withToken}
