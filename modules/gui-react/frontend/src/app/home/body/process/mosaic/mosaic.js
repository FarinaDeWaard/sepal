import {setAoiLayer} from 'app/home/map/aoiLayer'
import PropTypes from 'prop-types'
import React from 'react'
import {connect} from 'store'
import MapToolbar from './mapToolbar'
import styles from './mosaic.module.css'
import MosaicPreview from './mosaicPreview'
import {initRecipe, RecipeState} from './mosaicRecipe'
import Panels from './panels/panels'
import Toolbar from './panels/toolbar'

const mapStateToProps = (state, ownProps) => {
    const recipe = RecipeState(ownProps.recipeId)
    return {
        recipe: recipe()
    }
}

class Mosaic extends React.Component {
    render() {
        const {recipeId} = this.props
        return (
            <div className={styles.mosaic}>
                <MapToolbar recipeId={recipeId} className={[styles.toolbar, styles.map].join(' ')}/>
                <Toolbar recipeId={recipeId} className={[styles.toolbar, styles.mosaic].join(' ')}/>
                <Panels recipeId={recipeId} className={styles.panel}/>
                <MosaicPreview recipeId={recipeId}/>
            </div>
        )
    }

    componentDidMount() {
        const {recipeId, recipe: {aoi}, componentWillUnmount$} = this.props
        setAoiLayer({contextId: recipeId, aoi, destroy$: componentWillUnmount$})
    }
}

Mosaic.propTypes = {
    recipeId: PropTypes.string
}

export default connect(mapStateToProps)(Mosaic)
